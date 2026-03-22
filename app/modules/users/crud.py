from sqlalchemy.orm import Session

from app.modules.users.models import Permission, Rol, Usuario
from app.core.security import get_password_hash, verify_password
from app.modules.users.schemas import RolCreate, UsuarioCreate
from app.modules.users.permissions import PermissionCode


def crear_rol(db: Session, data: RolCreate) -> Rol:
    reserved = {"superadmin", "admin", "operador", "auditor"}
    if data.nombre in reserved:
        raise ValueError(f"rol reservado: {data.nombre}")

    unknown = sorted({p for p in data.permissions if p not in {c.value for c in PermissionCode}})
    if unknown:
        raise ValueError(f"permisos invalidos: {', '.join(unknown)}")

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
    rol = db.query(Rol).filter(Rol.id == data.rol_id).first()
    if not rol:
        raise ValueError("rol_id invalido")

    usuario = Usuario(
        username=data.username,
        email=str(data.email),
        nombre=data.nombre,
        apellido=data.apellido,
        rol_id=data.rol_id,
        password_hash=get_password_hash(data.password),
    )
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

    if usuario.is_superuser:
        raise ValueError("no se puede eliminar un superadmin")

    if not usuario.activo:
        return usuario

    usuario.activo = False
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
