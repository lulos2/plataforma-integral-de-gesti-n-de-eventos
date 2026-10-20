from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.deps import require_permissions, resolver_area_consulta, verificar_acceso_area
from app.modules.events import crud
from app.modules.events.presenter import to_audit_response, to_evento_response
from app.modules.users.models import Usuario
from .schemas import (
    AuditResponse,
    EstadisticasResponse,
    MotivoRequest,
    PuntoMapa,
    EventoResponse,
    EventoUpdate,
    EventoCreate,
    IntervencionCreate,
    IntervencionResponse,
    TipoEventoResponse,
)


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"]
)


def _evento_autorizado(db: Session, usuario: Usuario, evento_id: int):
    """Trae el evento: 404 si no existe, 403 si es de un area a la que el usuario no accede."""
    evento = crud.obtener_evento(db, evento_id)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    verificar_acceso_area(usuario, evento.tipo_evento.area)
    return evento


@router.get("/", response_model=list[EventoResponse])
def listar_eventos(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    estado: str | None = None,
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    limite: int | None = Query(default=None, ge=1, le=200),
    turno: str | None = None,
    direccion: str | None = None,
    especie: str | None = None,
    buscar: str | None = None,
):
    # Un usuario limitado a su area siempre consulta solo esa area (aunque pida otra o ninguna).
    area = resolver_area_consulta(usuario, area)

    eventos = crud.obtener_eventos(
        db,
        area=area,
        tipo_evento_id=tipo_evento_id,
        servicio_actuante_id=servicio_actuante_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limite=limite,
        turno=turno,
        direccion=direccion,
        especie=especie,
        buscar=buscar,
    )
    return [to_evento_response(e) for e in eventos]

@router.post("/", response_model=EventoResponse)
def crear_evento(
    data: EventoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:write")),
):
    tipo = crud.obtener_tipo_evento(db, tipo_evento_id=data.tipo_evento_id)
    if not tipo:
        raise HTTPException(status_code=400, detail="tipo_evento_id invalido")
    verificar_acceso_area(usuario, tipo.area)

    try:
        evento, _ = crud.crear_evento_base(
            db,
            tipo_evento_id=data.tipo_evento_id,
            data=data,
            actor_usuario_id=usuario.id,
        )
        db.commit()
        db.refresh(evento)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return to_evento_response(crud.obtener_evento(db, evento.id))


@router.get("/tipos", response_model=list[TipoEventoResponse])
def listar_tipos_evento(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
    area: str | None = None,
):
    return crud.listar_tipos_evento(db, area=resolver_area_consulta(usuario, area))


# Debe declararse antes de "/{evento_id}", si no "mapa" se interpreta como un id.
@router.get("/mapa", response_model=list[PuntoMapa])
def puntos_mapa(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("estadisticas:read")),
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    estado: str | None = None,
    turno: str | None = None,
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
):
    return crud.obtener_puntos_mapa(
        db,
        area=resolver_area_consulta(usuario, area),
        tipo_evento_id=tipo_evento_id,
        servicio_actuante_id=servicio_actuante_id,
        estado=estado,
        turno=turno,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


# Debe declararse antes de "/{evento_id}", si no "estadisticas" se interpreta como un id.
@router.get("/estadisticas", response_model=EstadisticasResponse)
def estadisticas(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("estadisticas:read")),
    area: str | None = None,
):
    return crud.obtener_estadisticas(db, area=resolver_area_consulta(usuario, area))


@router.get("/{evento_id}", response_model=EventoResponse)
def obtener_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
):
    return to_evento_response(_evento_autorizado(db, usuario, evento_id))


@router.put("/{evento_id}", response_model=EventoResponse)
def actualizar_evento(
    evento_id: int,
    data: EventoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:write")),
):
    _evento_autorizado(db, usuario, evento_id)

    try:
        evento = crud.actualizar_evento(db, evento_id, data, actor_usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return to_evento_response(evento)


# Los eventos no se eliminan: se anulan (queda el registro con su numero e historial).
@router.post("/{evento_id}/anular", response_model=EventoResponse)
def anular_evento(
    evento_id: int,
    data: MotivoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:anular")),
):
    _evento_autorizado(db, usuario, evento_id)

    try:
        evento = crud.anular_evento(db, evento_id, motivo=data.motivo, actor_usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return to_evento_response(evento)


@router.post("/{evento_id}/reabrir", response_model=EventoResponse)
def reabrir_evento(
    evento_id: int,
    data: MotivoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:reabrir")),
):
    _evento_autorizado(db, usuario, evento_id)

    try:
        evento = crud.reabrir_evento(db, evento_id, motivo=data.motivo, actor_usuario_id=usuario.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return to_evento_response(evento)


@router.get("/{evento_id}/historial", response_model=list[AuditResponse])
def historial_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
):
    _evento_autorizado(db, usuario, evento_id)
    return [to_audit_response(a) for a in crud.listar_historial(db, evento_id=evento_id)]


@router.post("/{evento_id}/intervenciones", response_model=IntervencionResponse)
def crear_intervencion(
    evento_id: int,
    data: IntervencionCreate,
    usuario: Annotated[Usuario, Depends(require_permissions("eventos:write"))],
    db: Session = Depends(get_db),
):
    _evento_autorizado(db, usuario, evento_id)

    try:
        intervencion = crud.crear_intervencion(
            db, evento_id=evento_id, data=data, actor_usuario_id=usuario.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not intervencion:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return intervencion


@router.get("/{evento_id}/intervenciones", response_model=list[IntervencionResponse])
def listar_intervenciones(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
):
    _evento_autorizado(db, usuario, evento_id)
    return crud.listar_intervenciones(db, evento_id=evento_id)
