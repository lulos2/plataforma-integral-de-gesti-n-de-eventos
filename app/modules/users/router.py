from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_admin_dios, require_permissions
from app.database.session import get_db
from app.modules.users import crud
from app.modules.users.schemas import (
    PermissionResponse,
    RolCreate,
    RolResponse,
    UsuarioCreate,
    UsuarioRolesUpdate,
    UsuarioResponse,
)


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("/roles", response_model=RolResponse)
def crear_rol(
    data: RolCreate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        return crud.crear_rol(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/roles/{rol_id}")
def eliminar_rol(
    rol_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        eliminado = crud.eliminar_rol(db, rol_id=rol_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not eliminado:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    return {"detail": "Rol eliminado"}


@router.get("/roles", response_model=list[RolResponse])
def listar_roles(
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("roles:read")),
):
    return crud.listar_roles(db)


@router.get("/permisos", response_model=list[PermissionResponse])
def listar_permisos(
    db: Session = Depends(get_db),
    _actor=Depends(require_permissions("roles:read")),
):
    return crud.listar_permisos(db)


@router.post("/", response_model=UsuarioResponse)
def crear_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
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


@router.patch("/{usuario_id}/roles", response_model=UsuarioResponse)
def actualizar_roles_usuario(
    usuario_id: int,
    data: UsuarioRolesUpdate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        usuario = crud.actualizar_roles_usuario(db, usuario_id=usuario_id, rol_ids=data.rol_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


@router.delete("/{usuario_id}", response_model=UsuarioResponse)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        eliminado = crud.eliminar_usuario(db, usuario_id=usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not eliminado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return eliminado
