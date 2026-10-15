from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import areas_accesibles, get_current_user, permisos_efectivos
from app.core.security import create_access_token
from app.database.session import get_db
from app.modules.users import crud as users_crud
from app.modules.users.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UsuarioMeResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = users_crud.autenticar_usuario(db, username=form_data.username, password=form_data.password)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o password incorrectos",
        )
    token = create_access_token(subject=str(usuario.id), session_version=usuario.session_version)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UsuarioMeResponse)
def me(usuario=Depends(get_current_user)):
    roles = sorted(r.nombre for r in usuario.roles)
    return UsuarioMeResponse.model_validate(usuario).model_copy(
        update={
            "rol": roles[0] if roles else None,
            "permisos": permisos_efectivos(usuario),
            "areas_acceso": areas_accesibles(usuario),
        }
    )


@router.post("/forgot-password", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
def forgot_password(data: ForgotPasswordRequest):
    # No emitir tokens hasta contar con un canal de entrega que verifique al titular.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Recuperacion de contrasena temporalmente no disponible",
    )


@router.post("/reset-password", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
def reset_password(data: ResetPasswordRequest):
    # Los tokens de la version demo pudieron obtenerse sin verificar identidad.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Recuperacion de contrasena temporalmente no disponible",
    )

