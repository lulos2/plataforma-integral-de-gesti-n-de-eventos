from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_token_subject
from app.modules.users import crud as users_crud
from app.modules.users.models import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


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


def require_superuser(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if not usuario.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere superadmin")
    return usuario


def _user_permission_codes(usuario: Usuario) -> set[str]:
    if usuario.is_superuser:
        # Superuser bypass.
        return {"*"}
    rol = getattr(usuario, "rol", None)
    if not rol:
        return set()
    perms = getattr(rol, "permissions", None) or []
    return {p.code for p in perms if getattr(p, "code", None)}


def require_permissions(*required: str):
    """
    Dependency factory. Requires ALL permissions unless user is superuser.
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
