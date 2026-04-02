from sqlalchemy.orm import Session

from app.modules.users.models import Permission, Rol, Usuario
from app.core.security import get_password_hash, verify_password
from app.modules.users.schemas import RolCreate, UsuarioCreate
from app.modules.users.permissions import PermissionCode


def crear_rol(db: Session, data: RolCreate) -> Rol:
    reserved = {"adminDios", "superadmin", "admin", "operador", "auditor"}
    if data.nombre in reserved:
        raise ValueError(f"rol reservado: {data.nombre}")

    unknown = sorted({p for p in data.permissions if p not in {c.value for c in PermissionCode}})
    if unknown:
        raise ValueError(f"permisos invalidos: {', '.join(unknown)}")
    if data.permissions:
        all_permission_codes = {row[0] for row in db.query(Permission.code).all()}
        if all_permission_codes and set(data.permissions) == all_permission_codes:
            raise ValueError("no se puede crear otro rol con todos los permisos")

    rol = Rol(nombre=data.nombre)
    if data.permissions:
        permisos = (
            db.query(Permission)
            .filter(Permission.code.in_(data.permissions))
            .all()
        )
        found = {p.code for p in permisos}
        missing = sorted(set(data.permissions) - found)
        if missing:
            # Should not happen if seeding ran, but keep a clear error.
            raise ValueError(f"permisos inexistentes en DB: {', '.join(missing)}")
        rol.permissions = permisos

    db.add(rol)
    db.commit()
    db.refresh(rol)
    return rol


def listar_roles(db: Session) -> list[Rol]:
    return db.query(Rol).order_by(Rol.nombre.asc()).all()


def crear_usuario(db: Session, data: UsuarioCreate) -> Usuario:
    roles = db.query(Rol).filter(Rol.id.in_(data.rol_ids)).all()
    found_ids = {r.id for r in roles}
    missing_ids = sorted(set(data.rol_ids) - found_ids)
    if missing_ids:
        raise ValueError(f"rol_ids invalidos: {', '.join(map(str, missing_ids))}")

    selected_admin_dios = any(r.nombre == "adminDios" for r in roles)
    if selected_admin_dios:
        existing_admin_dios = (
            db.query(Usuario.id)
            .join(Usuario.roles)
            .filter(Rol.nombre == "adminDios")
            .first()
        )
        if existing_admin_dios:
            raise ValueError("solo puede existir un usuario con rol adminDios")

    usuario = Usuario(
        username=data.username,
        email=str(data.email),
        nombre=data.nombre,
        apellido=data.apellido,
        password_hash=get_password_hash(data.password),
    )
    usuario.roles = roles
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def listar_usuarios(db: Session) -> list[Usuario]:
    return db.query(Usuario).order_by(Usuario.id.desc()).all()


def eliminar_usuario(db: Session, *, usuario_id: int) -> Usuario | None:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        return None

    role_names = {r.nombre for r in (getattr(usuario, "roles", None) or [])}
    if "adminDios" in role_names:
        raise ValueError("no se puede eliminar un usuario con rol adminDios")

    if not usuario.activo:
        return usuario

    usuario.activo = False
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def eliminar_rol(db: Session, *, rol_id: int) -> bool:
    rol = db.query(Rol).filter(Rol.id == rol_id).first()
    if not rol:
        return False
    if rol.nombre == "adminDios":
        raise ValueError("no se puede eliminar el rol adminDios")

    has_users = db.query(Usuario.id).join(Usuario.roles).filter(Rol.id == rol.id).first()
    if has_users:
        raise ValueError("no se puede eliminar un rol asignado a usuarios")

    db.delete(rol)
    db.commit()
    return True


def actualizar_roles_usuario(db: Session, *, usuario_id: int, rol_ids: list[int]) -> Usuario | None:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        return None

    roles = db.query(Rol).filter(Rol.id.in_(rol_ids)).all()
    found_ids = {r.id for r in roles}
    missing_ids = sorted(set(rol_ids) - found_ids)
    if missing_ids:
        raise ValueError(f"rol_ids invalidos: {', '.join(map(str, missing_ids))}")

    current_has_admin_dios = any(r.nombre == "adminDios" for r in usuario.roles)
    target_has_admin_dios = any(r.nombre == "adminDios" for r in roles)

    if target_has_admin_dios and not current_has_admin_dios:
        existing_admin_dios = (
            db.query(Usuario.id)
            .join(Usuario.roles)
            .filter(Rol.nombre == "adminDios", Usuario.id != usuario.id)
            .first()
        )
        if existing_admin_dios:
            raise ValueError("solo puede existir un usuario con rol adminDios")

    if current_has_admin_dios and not target_has_admin_dios:
        raise ValueError("no se puede quitar el rol adminDios al usuario adminDios")

    usuario.roles = roles
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def obtener_usuario_por_username(db: Session, username: str) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.username == username).first()


def obtener_usuario_por_id(db: Session, usuario_id: int) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.id == usuario_id).first()


def autenticar_usuario(db: Session, *, username: str, password: str) -> Usuario | None:
    usuario = obtener_usuario_por_username(db, username)
    if not usuario or not usuario.password_hash:
        return None
    if not verify_password(password, usuario.password_hash):
        return None
    if not usuario.activo:
        return None
    return usuario
