from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin_dios
from app.database.session import get_db
from app.modules.events.presenter import to_evento_response
from app.modules.events.schemas import EventoResponse
from app.modules.poligonos import crud
from app.modules.poligonos.schemas import (
    PoligonoCreate,
    PoligonoResponse,
    PoligonoUpdate,
)


router = APIRouter(prefix="/poligonos", tags=["Poligonos"])


@router.post("/", response_model=PoligonoResponse)
def crear_poligono(
    data: PoligonoCreate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        return crud.crear_poligono(db, data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[PoligonoResponse])
def listar_poligonos(
    db: Session = Depends(get_db),
    _actor=Depends(get_current_user),
):
    return crud.listar_poligonos(db)


@router.get("/{poligono_id}/eventos", response_model=list[EventoResponse])
def listar_eventos_en_poligono(
    poligono_id: int,
    db: Session = Depends(get_db),
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    _actor=Depends(get_current_user),
):
    if area and tipo_evento_id is not None:
        raise HTTPException(status_code=400, detail="usar solo uno: area o tipo_evento_id")

    poligono = crud.obtener_poligono(db, poligono_id=poligono_id)
    if not poligono:
        raise HTTPException(status_code=404, detail="Poligono no encontrado")

    eventos = crud.listar_eventos_en_poligono(
        db,
        poligono_id=poligono_id,
        area=area,
        tipo_evento_id=tipo_evento_id,
        servicio_actuante_id=servicio_actuante_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    return [to_evento_response(e) for e in eventos]


@router.get("/{poligono_id}", response_model=PoligonoResponse)
def obtener_poligono(
    poligono_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(get_current_user),
):
    poligono = crud.obtener_poligono(db, poligono_id=poligono_id)
    if not poligono:
        raise HTTPException(status_code=404, detail="Poligono no encontrado")
    return poligono


@router.put("/{poligono_id}", response_model=PoligonoResponse)
def actualizar_poligono(
    poligono_id: int,
    data: PoligonoUpdate,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    try:
        poligono = crud.actualizar_poligono(db, poligono_id=poligono_id, data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not poligono:
        raise HTTPException(status_code=404, detail="Poligono no encontrado")
    return poligono


@router.delete("/{poligono_id}")
def eliminar_poligono(
    poligono_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_admin_dios),
):
    eliminado = crud.eliminar_poligono(db, poligono_id=poligono_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Poligono no encontrado")
    return {"detail": "Poligono eliminado"}
