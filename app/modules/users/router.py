from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import (
    es_admin_dios,
    require_admin_dios,
    require_permissions,
    resolver_area_consulta,
    verificar_acceso_area,
    verificar_gestion_usuario,
)
from app.database.session import get_db
from app.modules.users import crud
from app.modules.users.schemas import (
    PermissionResponse,
    RolCreate,
    RolResponse,
    UsuarioActivoUpdate,
    UsuarioAreaUpdate,
    UsuarioCreate,
    UsuarioDatosUpdate,
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
    actor=Depends(require_permissions("users:write")),
):
    if not es_admin_dios(actor):
        # El administrador de area solo crea operadores y siempre dentro de su propia area.
        if not actor.area:
            raise HTTPException(status_code=403, detail="El usuario no tiene un area asignada")
        if data.area and data.area != actor.area:
            raise HTTPException(status_code=403, detail="Solo puede crear usuarios de su area")
        roles = crud.obtener_roles_por_ids(db, data.rol_ids)
        if any(r.nombre != "operador" for r in roles):
            raise HTTPException(status_code=403, detail="Solo puede crear cuentas de operadores")
        data = data.model_copy(update={"area": actor.area})

    try:
        return crud.crear_usuario(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(
    db: Session = Depends(get_db),
    actor=Depends(require_permissions("users:read")),
    area: str | None = None,
):
    # Quien no ve todas las areas solo lista los usuarios de la suya.
    return crud.listar_usuarios(db, area=resolver_area_consulta(actor, area))


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    actor=Depends(require_permissions("users:read")),
):
    usuario = crud.obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_acceso_area(actor, usuario.area)
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


@router.patch("/{usuario_id}/area", response_model=UsuarioResponse)
def actualizar_area_usuario(
    usuario_id: int,
    data: UsuarioAreaUpdate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        usuario = crud.actualizar_area_usuario(db, usuario_id=usuario_id, area=data.area)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


def _usuario_administrable(db: Session, actor, usuario_id: int):
    usuario = crud.obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    verificar_gestion_usuario(actor, usuario)
    return usuario


@router.patch("/{usuario_id}/datos", response_model=UsuarioResponse)
def actualizar_datos_usuario(
    usuario_id: int,
    data: UsuarioDatosUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_permissions("users:write")),
):
    # Nombre, apellido y correo. El administrador de area solo puede en operadores de su area.
    _usuario_administrable(db, actor, usuario_id)
    try:
        return crud.actualizar_datos_usuario(
            db, usuario_id=usuario_id, cambios=data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{usuario_id}/activo", response_model=UsuarioResponse)
def actualizar_activo_usuario(
    usuario_id: int,
    data: UsuarioActivoUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_permissions("users:write")),
):
    _usuario_administrable(db, actor, usuario_id)
    try:
        usuario = crud.actualizar_activo_usuario(db, usuario_id=usuario_id, activo=data.activo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return usuario


@router.delete("/{usuario_id}", response_model=UsuarioResponse)
def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    actor=Depends(require_permissions("users:write")),
):
    _usuario_administrable(db, actor, usuario_id)
    try:
        eliminado = crud.eliminar_usuario(db, usuario_id=usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return eliminado
