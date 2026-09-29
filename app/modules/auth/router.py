from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import create_access_token
from app.core.deps import get_current_user
from app.modules.users import crud as users_crud
from app.modules.users.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    UsuarioResponse,
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
    token = create_access_token(subject=str(usuario.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UsuarioResponse)
def me(usuario=Depends(get_current_user)):
    return usuario


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    try:
        resultado = users_crud.solicitar_reset_password(db, username=data.username, email=data.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resultado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario, raw_token, expira_en = resultado
    return ForgotPasswordResponse(
        mensaje=(
            f"Token de recuperacion generado para {usuario.username}. "
            "Modo demo: en produccion esto se enviaria por email, no se devolveria aca."
        ),
        reset_token=raw_token,
        expira_en=expira_en,
    )


@router.post("/reset-password", response_model=UsuarioResponse)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    try:
        usuario = users_crud.resetear_password(db, token=data.token, password_nueva=data.password_nueva)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return usuario

