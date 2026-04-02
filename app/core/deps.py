from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_token_subject
from app.modules.users import crud as users_crud
from app.modules.users.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
ADMIN_DIOS_ROLE_NAME = "adminDios"


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    sub = decode_token_subject(token)
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")
    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    usuario = users_crud.obtener_usuario_por_id(db, user_id)
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autorizado")
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
