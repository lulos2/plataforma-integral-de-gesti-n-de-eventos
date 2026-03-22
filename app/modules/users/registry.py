from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import get_password_hash
from app.modules.users.models import Permission, Rol, Usuario
from app.modules.users.permissions import PERMISSION_DESCRIPTIONS, PermissionCode


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
    "admin": (PermissionCode.ROLES_READ, PermissionCode.USERS_READ, PermissionCode.USERS_WRITE),
    "operador": (PermissionCode.USERS_READ,),
    "auditor": (PermissionCode.ROLES_READ, PermissionCode.USERS_READ),
}


def ensure_superadmin_role(db: Session) -> Rol:
    role = db.query(Rol).filter(Rol.nombre == "superadmin").first()
    if role:
        return role

    perms = db.query(Permission).all()
    role = Rol(nombre="superadmin", permissions=perms)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


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
    ensure that user exists, is active, is_superuser, and belongs to the superadmin role.
    """
    username = settings.bootstrap_superadmin_username
    password = settings.bootstrap_superadmin_password
    if not username or not password:
        return

    super_role = ensure_superadmin_role(db)

    user = db.query(Usuario).filter(Usuario.username == username).first()
    if user:
        changed = False
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.activo:
            user.activo = True
            changed = True
        if user.rol_id != super_role.id:
            user.rol_id = super_role.id
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
        rol_id=super_role.id,
        password_hash=get_password_hash(password),
        is_superuser=True,
        activo=True,
    )
    db.add(user)
    db.commit()
