from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_permissions, verificar_acceso_area
from app.database.session import get_db
from app.modules.events import crud as events_crud
from app.modules.events.presenter import to_evento_response
from app.modules.events.schemas import EventoResponse
from app.modules.videoseguridad import crud
from app.modules.videoseguridad.schemas import EventoVideoseguridadCreate, EventoVideoseguridadUpdate


router = APIRouter(prefix="/videoseguridad", tags=["Videoseguridad"])


@router.post("/eventos/{tipo}", response_model=EventoResponse)
def crear_evento_videoseguridad(
    tipo: str,
    data: EventoVideoseguridadCreate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:write")),
):
    verificar_acceso_area(usuario, "videoseguridad")

    try:
        creado = crud.crear_evento_videoseguridad(db, tipo_nombre=tipo, data=data, actor_usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    creado = events_crud.obtener_evento(db, creado.id)
    return to_evento_response(creado)


@router.put("/eventos/{evento_id}", response_model=EventoResponse)
def actualizar_evento_videoseguridad(
    evento_id: int,
    data: EventoVideoseguridadUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:write")),
):
    existente = events_crud.obtener_evento(db, evento_id)
    if existente:
        verificar_acceso_area(usuario, existente.tipo_evento.area)
        events_crud.verificar_no_anulado(existente)

    try:
        actualizado = crud.actualizar_evento_videoseguridad(
            db, evento_id=evento_id, data=data, actor_usuario_id=usuario.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not actualizado:
        raise HTTPException(status_code=404, detail="Evento de videoseguridad no encontrado")

    return to_evento_response(events_crud.obtener_evento(db, evento_id))

