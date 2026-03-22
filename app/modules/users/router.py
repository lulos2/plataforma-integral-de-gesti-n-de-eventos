from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_permissions, require_superuser
from app.database.session import get_db
from app.modules.users import crud
from app.modules.users.schemas import (
    RolCreate,
    RolResponse,
    UsuarioCreate,
    UsuarioResponse,
)


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("/roles", response_model=RolResponse)
def crear_rol(
    data: RolCreate,
    db: Session = Depends(get_db),
    _actor=Depends(require_superuser),
):
    return crud.crear_rol(db, data)


@router.get("/roles", response_model=list[RolResponse])
def listar_roles(
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("roles:read")),
):
    return crud.listar_roles(db)


@router.post("/", response_model=UsuarioResponse)
def crear_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("users:write")),
):
    try:
        return crud.crear_usuario(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("users:read")),
):
    return crud.listar_usuarios(db)


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("users:read")),
):
    usuario = crud.obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


@router.delete("/{usuario_id}", response_model=UsuarioResponse)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_superuser),
):
    try:
        eliminado = crud.eliminar_usuario(db, usuario_id=usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not eliminado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return eliminado
