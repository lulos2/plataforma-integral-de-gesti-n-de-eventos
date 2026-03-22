from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.deps import get_current_user
from app.modules.events import crud
from app.modules.events.presenter import to_evento_response
from .schemas import (
    EventoResponse,
    EventoUpdate,
    IntervencionCreate,
    IntervencionResponse,
    TipoEventoResponse,
)


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"]
)


@router.get("/", response_model=list[EventoResponse])
def listar_eventos(
    db: Session = Depends(get_db),
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
):

    eventos = crud.obtener_eventos(
        db,
        area=area,
        tipo_evento_id=tipo_evento_id,
        servicio_actuante_id=servicio_actuante_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    return [to_evento_response(e) for e in eventos]


@router.get("/{evento_id}", response_model=EventoResponse)
def obtener_evento(
    evento_id: int,
    db: Session = Depends(get_db)
):

    evento = crud.obtener_evento(db, evento_id)

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return to_evento_response(evento)


@router.put("/{evento_id}", response_model=EventoResponse)
def actualizar_evento(
    evento_id: int,
    data: EventoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        evento = crud.actualizar_evento(db, evento_id, data, actor_usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return to_evento_response(evento)


@router.delete("/{evento_id}")
def eliminar_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    evento = crud.eliminar_evento(db, evento_id=evento_id, actor_usuario_id=usuario.id)

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return {"mensaje": "Evento eliminado"}


@router.post("/{evento_id}/intervenciones", response_model=IntervencionResponse)
def crear_intervencion(
    evento_id: int,
    data: IntervencionCreate,
    db: Session = Depends(get_db),
):
    try:
        intervencion = crud.crear_intervencion(db, evento_id=evento_id, data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not intervencion:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return intervencion


@router.get("/{evento_id}/intervenciones", response_model=list[IntervencionResponse])
def listar_intervenciones(
    evento_id: int,
    db: Session = Depends(get_db),
):
    return crud.listar_intervenciones(db, evento_id=evento_id)


@router.get("/tipos", response_model=list[TipoEventoResponse])
def listar_tipos_evento(
    db: Session = Depends(get_db),
    area: str | None = None,
):
    return crud.listar_tipos_evento(db, area=area)
