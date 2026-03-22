from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.modules.events.models import Evento, EventoAudit, TipoEvento
from app.modules.events.models_domain import EventoIntervencion, EventoVideoseguridad, ServicioActuante


class _EventoBaseData(Protocol):
    descripcion: str | None
    fuente: str
    estado: str
    fecha_ocurrencia: datetime | None
    latitud: float
    longitud: float


def _crear_audit(db: Session, *, evento_id: int, actor_usuario_id: int, accion: str, detalle: dict | None = None):
    db.add(
        EventoAudit(
            evento_id=evento_id,
            actor_usuario_id=actor_usuario_id,
            accion=accion,
            detalle=detalle,
        )
    )


def obtener_tipo_evento(db: Session, *, tipo_evento_id: int) -> TipoEvento | None:
    return db.query(TipoEvento).filter(TipoEvento.id == tipo_evento_id).first()


def obtener_tipo_evento_por_area_nombre(db: Session, *, area: str, nombre: str) -> TipoEvento | None:
    return (
        db.query(TipoEvento)
        .filter(TipoEvento.area == area, TipoEvento.nombre == nombre)
        .first()
    )


def crear_evento_base(
    db: Session,
    *,
    tipo_evento_id: int,
    data: _EventoBaseData,
    actor_usuario_id: int,
) -> tuple[Evento, TipoEvento]:

    tipo = obtener_tipo_evento(db, tipo_evento_id=tipo_evento_id)
    if not tipo:
        raise ValueError("tipo_evento_id invalido")

    point = from_shape(Point(data.longitud, data.latitud), srid=4326)

    evento = Evento(
        tipo_evento_id=tipo_evento_id,
        descripcion=data.descripcion,
        fuente=data.fuente,
        estado=data.estado,
        fecha_ocurrencia=data.fecha_ocurrencia,
        latitud=data.latitud,
        longitud=data.longitud,
        ubicacion=point,
        usuario_id=actor_usuario_id,
    )

    db.add(evento)
    db.flush()  # assign evento.id without committing
    return evento, tipo


def obtener_eventos(
    db: Session,
    *,
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
):

    q = db.query(Evento).options(joinedload(Evento.tipo_evento))

    if area:
        q = q.join(Evento.tipo_evento).filter(TipoEvento.area == area)

    if tipo_evento_id:
        q = q.filter(Evento.tipo_evento_id == tipo_evento_id)

    if servicio_actuante_id:
        q = q.join(EventoVideoseguridad, EventoVideoseguridad.evento_id == Evento.id).filter(
            EventoVideoseguridad.servicio_actuante_id == servicio_actuante_id
        )

    if fecha_desde:
        q = q.filter(Evento.fecha_ocurrencia >= fecha_desde)

    if fecha_hasta:
        q = q.filter(Evento.fecha_ocurrencia <= fecha_hasta)

    return q.order_by(Evento.fecha_creacion.desc()).all()


def obtener_evento(db: Session, evento_id: int) -> Evento | None:

    return (
        db.query(Evento)
        .options(joinedload(Evento.tipo_evento))
        .filter(Evento.id == evento_id)
        .first()
    )


def crear_intervencion(db: Session, *, evento_id: int, data):
    evento = db.query(Evento).filter(Evento.id == evento_id).first()
    if not evento:
        return None

    servicio = db.query(ServicioActuante).filter(ServicioActuante.id == data.servicio_actuante_id).first()
    if not servicio:
        raise ValueError("servicio_actuante_id invalido")

    intervencion = EventoIntervencion(
        evento_id=evento_id,
        servicio_actuante_id=data.servicio_actuante_id,
        actor_usuario_id=data.actor_usuario_id,
        asignado_en=data.asignado_en,
        arribo_en=data.arribo_en,
        cerrado_en=data.cerrado_en,
        notas=data.notas,
        extra=data.extra,
    )
    db.add(intervencion)
    db.commit()
    db.refresh(intervencion)
    return intervencion


def listar_intervenciones(db: Session, *, evento_id: int):
    return (
        db.query(EventoIntervencion)
        .filter(EventoIntervencion.evento_id == evento_id)
        .order_by(EventoIntervencion.fecha_creacion.desc())
        .all()
    )


def actualizar_evento(db: Session, evento_id: int, data, *, actor_usuario_id: int):

    evento = db.query(Evento).filter(Evento.id == evento_id).first()
    if not evento:
        return None

    detalle = {}

    for campo in ("descripcion", "fuente", "estado", "fecha_ocurrencia"):
        nuevo = getattr(data, campo)
        if nuevo is not None and nuevo != getattr(evento, campo):
            detalle[campo] = {"from": getattr(evento, campo), "to": nuevo}
            setattr(evento, campo, nuevo)

    if data.latitud is not None or data.longitud is not None:
        nueva_lat = evento.latitud if data.latitud is None else data.latitud
        nueva_lon = evento.longitud if data.longitud is None else data.longitud
        if nueva_lat != evento.latitud or nueva_lon != evento.longitud:
            detalle["ubicacion"] = {"from": [evento.latitud, evento.longitud], "to": [nueva_lat, nueva_lon]}
            evento.latitud = nueva_lat
            evento.longitud = nueva_lon
            evento.ubicacion = from_shape(Point(nueva_lon, nueva_lat), srid=4326)

    db.add(evento)
    db.commit()
    db.refresh(evento)

    if detalle:
        _crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="update", detalle=detalle)
        db.commit()

    return obtener_evento(db, evento.id)


def eliminar_evento(db: Session, *, evento_id: int, actor_usuario_id: int):

    evento = db.query(Evento).filter(Evento.id == evento_id).first()

    if evento:
        _crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="delete")
        db.delete(evento)
        db.commit()

    return evento


def listar_tipos_evento(db: Session, *, area: str | None = None):
    q = db.query(TipoEvento)
    if area:
        q = q.filter(TipoEvento.area == area)
    return q.order_by(TipoEvento.area.asc(), TipoEvento.nombre.asc()).all()
