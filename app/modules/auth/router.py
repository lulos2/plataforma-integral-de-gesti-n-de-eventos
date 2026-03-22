from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import create_access_token
from app.core.deps import get_current_user
from app.modules.users import crud as users_crud
from app.modules.users.schemas import UsuarioResponse

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

