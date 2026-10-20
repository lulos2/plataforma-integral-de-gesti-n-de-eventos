from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.areas import AREAS_VALIDAS, normalizar_area
from app.core.security import decode_access_token
from app.database.session import get_db
from app.modules.users import crud as users_crud
from app.modules.users.models import Usuario
from app.modules.users.permissions import PermissionCode

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
ADMIN_DIOS_ROLE_NAME = "adminDios"
OPERADOR_ROLE_NAME = "operador"


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")
    try:
        user_id = int(payload["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido"
        ) from None

    usuario = users_crud.obtener_usuario_por_id(db, user_id)
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autorizado")
    if payload["session_version"] != usuario.session_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion invalidada")
    return usuario


def _is_admin_dios(usuario: Usuario) -> bool:
    roles = getattr(usuario, "roles", None) or []
    return any(getattr(rol, "nombre", None) == ADMIN_DIOS_ROLE_NAME for rol in roles)


def require_admin_dios(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if not _is_admin_dios(usuario):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol adminDios")
    return usuario


def _user_permission_codes(usuario: Usuario) -> set[str]:
    if _is_admin_dios(usuario):
        # adminDios bypass.
        return {"*"}
    roles = getattr(usuario, "roles", None) or []
    codes: set[str] = set()
    for rol in roles:
        perms = getattr(rol, "permissions", None) or []
        codes.update({p.code for p in perms if getattr(p, "code", None)})
    return codes


def permisos_efectivos(usuario: Usuario) -> list[str]:
    """Lista de permisos que realmente tiene el usuario (adminDios: todos)."""
    codes = _user_permission_codes(usuario)
    if "*" in codes:
        return sorted(c.value for c in PermissionCode)
    return sorted(codes)


def areas_accesibles(usuario: Usuario) -> list[str]:
    """Areas cuyos datos puede ver: todas, solo la suya o ninguna si no tiene area asignada."""
    if tiene_acceso_a_todas_las_areas(usuario):
        return list(AREAS_VALIDAS)
    return [usuario.area] if usuario.area else []


def tiene_acceso_a_todas_las_areas(usuario: Usuario) -> bool:
    codes = _user_permission_codes(usuario)
    return "*" in codes or PermissionCode.AREAS_ALL.value in codes


def verificar_acceso_area(usuario: Usuario, area: str | None) -> None:
    """Corta con 403 si el usuario no puede acceder a datos de esa area."""
    if tiene_acceso_a_todas_las_areas(usuario):
        return
    if not usuario.area:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene un area asignada",
        )
    if area != usuario.area:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a datos de esa area",
        )


def resolver_area_consulta(usuario: Usuario, area: str | None) -> str | None:
    """
    Area por la que hay que filtrar una consulta.

    Con acceso a todas las areas devuelve lo que pidio (None = sin filtro). Si no, fuerza el area
    del usuario y rechaza pedir otra.
    """
    area = normalizar_area(area)
    if tiene_acceso_a_todas_las_areas(usuario):
        return area
    verificar_acceso_area(usuario, area or usuario.area)
    return usuario.area


def es_admin_dios(usuario: Usuario) -> bool:
    return _is_admin_dios(usuario)


def verificar_gestion_usuario(actor: Usuario, objetivo: Usuario) -> None:
    """
    Corta con 403 si el actor no puede administrar la cuenta del objetivo.

    adminDios administra cualquier cuenta. Un administrador de area solo administra operadores
    de su propia area.
    """
    if _is_admin_dios(actor):
        return
    if not actor.area or objetivo.area != actor.area:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puede administrar usuarios de su area",
        )
    if any(getattr(r, "nombre", None) != OPERADOR_ROLE_NAME for r in objetivo.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puede administrar cuentas de operadores",
        )


def require_permissions(*required: str):
    """
    Dependency factory. Requires ALL permissions unless user has adminDios role.
    """

    def _dep(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        codes = _user_permission_codes(usuario)
        if "*" in codes:
            return usuario
        missing = [p for p in required if p not in codes]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes: {', '.join(missing)}",
            )
        return usuario

    return _dep
