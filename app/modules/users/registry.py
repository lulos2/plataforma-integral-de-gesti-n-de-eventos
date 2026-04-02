from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import get_password_hash
from app.modules.users.models import Permission, Rol, Usuario
from app.modules.users.permissions import PERMISSION_DESCRIPTIONS, PermissionCode


ADMIN_DIOS_ROLE_NAME = "adminDios"


def _admin_dios_users(db: Session) -> list[Usuario]:
    return (
        db.query(Usuario)
        .join(Usuario.roles)
        .filter(Rol.nombre == ADMIN_DIOS_ROLE_NAME)
        .order_by(Usuario.id.asc())
        .all()
    )


def sync_permissions(db: Session) -> None:
    existing = {row[0] for row in db.query(Permission.code).all()}
    missing = [c for c in PermissionCode if c.value not in existing]
    if not missing:
        return

    db.add_all(
        [
            Permission(code=code.value, description=PERMISSION_DESCRIPTIONS.get(code))
            for code in missing
        ]
    )
    db.commit()


SYSTEM_ROLES: dict[str, tuple[PermissionCode, ...]] = {
    ADMIN_DIOS_ROLE_NAME: tuple(PermissionCode),
    "admin": (PermissionCode.ROLES_READ, PermissionCode.USERS_READ, PermissionCode.USERS_WRITE),
    "operador": (PermissionCode.USERS_READ,),
    "auditor": (PermissionCode.ROLES_READ, PermissionCode.USERS_READ),
}


def ensure_admin_dios_role(db: Session) -> Rol:
    role = db.query(Rol).filter(Rol.nombre == ADMIN_DIOS_ROLE_NAME).first()
    if role:
        return role

    perms = db.query(Permission).all()
    role = Rol(nombre=ADMIN_DIOS_ROLE_NAME, permissions=perms)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def ensure_single_admin_dios_user(db: Session) -> None:
    """
    Guarantee at most one user with adminDios role.
    If duplicates exist, keep the oldest and demote the rest.
    """
    admin_dios_role = ensure_admin_dios_role(db)
    admin_dios_users = _admin_dios_users(db)
    if len(admin_dios_users) <= 1:
        return

    fallback_role = db.query(Rol).filter(Rol.nombre == "admin").first()
    if not fallback_role:
        fallback_role = (
            db.query(Rol)
            .filter(Rol.id != admin_dios_role.id)
            .order_by(Rol.id.asc())
            .first()
        )
    if not fallback_role:
        raise RuntimeError("No existe un rol alternativo para reasignar adminDios duplicados")

    for duplicate in admin_dios_users[1:]:
        duplicate.roles = [r for r in duplicate.roles if r.id != admin_dios_role.id]
        if not any(r.id == fallback_role.id for r in duplicate.roles):
            duplicate.roles.append(fallback_role)
        db.add(duplicate)
    db.commit()


def migrate_legacy_superadmin_users(db: Session) -> None:
    """
    Migrate legacy privilege model (superadmin role / is_superuser flag)
    into the adminDios role.
    """
    admin_dios_role = ensure_admin_dios_role(db)
    if db.bind and db.bind.dialect.name == "postgresql":
        has_rol_id_column = db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'usuarios'
                      AND column_name = 'rol_id'
                )
                """
            )
        ).scalar()
        if has_rol_id_column:
            db.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT id, rol_id
                    FROM usuarios
                    WHERE rol_id IS NOT NULL
                    ON CONFLICT DO NOTHING
                    """
                )
            )
            db.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT ur.user_id, :admin_dios_role_id
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE r.nombre = 'superadmin'
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"admin_dios_role_id": admin_dios_role.id},
            )

        has_legacy_column = db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'usuarios'
                      AND column_name = 'is_superuser'
                )
                """
            )
        ).scalar()
        if has_legacy_column:
            db.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT id, :admin_dios_role_id
                    FROM usuarios
                    WHERE is_superuser = TRUE
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"admin_dios_role_id": admin_dios_role.id},
            )
        db.commit()

    legacy_role = db.query(Rol).filter(Rol.nombre == "superadmin").first()
    if legacy_role:
        superadmin_users = (
            db.query(Usuario)
            .join(Usuario.roles)
            .filter(Rol.id == legacy_role.id)
            .all()
        )
        for user in superadmin_users:
            if not any(r.id == admin_dios_role.id for r in user.roles):
                user.roles.append(admin_dios_role)
            user.roles = [r for r in user.roles if r.id != legacy_role.id]
            db.add(user)
        db.commit()


def sync_system_roles(db: Session) -> None:
    """
    Create/update system roles to prevent "role name implies permissions" drift.
    """
    for role_name, perm_codes in SYSTEM_ROLES.items():
        role = db.query(Rol).filter(Rol.nombre == role_name).first()
        perms = db.query(Permission).filter(Permission.code.in_([p.value for p in perm_codes])).all()
        if role:
            role.permissions = perms
            db.add(role)
        else:
            db.add(Rol(nombre=role_name, permissions=perms))
    db.commit()


def bootstrap_superadmin(db: Session, settings: Settings) -> None:
    """
    Optional bootstrap for initial privilege management.

    If BOOTSTRAP_SUPERADMIN_USERNAME and BOOTSTRAP_SUPERADMIN_PASSWORD are set,
    ensure that user exists, is active, and belongs to the adminDios role.
    """
    username = settings.bootstrap_superadmin_username
    password = settings.bootstrap_superadmin_password
    if not username or not password:
        return

    admin_dios_role = ensure_admin_dios_role(db)
    ensure_single_admin_dios_user(db)
    existing_admin_dios = _admin_dios_users(db)
    primary_admin_dios = existing_admin_dios[0] if existing_admin_dios else None

    user = db.query(Usuario).filter(Usuario.username == username).first()
    if primary_admin_dios and user and user.id != primary_admin_dios.id:
        # Preserve uniqueness: do not promote another user to adminDios.
        changed = False
        if not primary_admin_dios.activo:
            primary_admin_dios.activo = True
            changed = True
        if not primary_admin_dios.password_hash:
            primary_admin_dios.password_hash = get_password_hash(password)
            changed = True
        if changed:
            db.add(primary_admin_dios)
            db.commit()
        return

    if primary_admin_dios and not user:
        changed = False
        if not primary_admin_dios.activo:
            primary_admin_dios.activo = True
            changed = True
        if not primary_admin_dios.password_hash:
            primary_admin_dios.password_hash = get_password_hash(password)
            changed = True
        if changed:
            db.add(primary_admin_dios)
            db.commit()
        return

    if user:
        changed = False
        if not user.activo:
            user.activo = True
            changed = True
        if not any(r.id == admin_dios_role.id for r in user.roles):
            user.roles.append(admin_dios_role)
            changed = True
        if not user.password_hash:
            user.password_hash = get_password_hash(password)
            changed = True
        if changed:
            db.add(user)
            db.commit()
        return

    user = Usuario(
        username=username,
        email=None,
        password_hash=get_password_hash(password),
        activo=True,
        roles=[admin_dios_role],
    )
    db.add(user)
    db.commit()
