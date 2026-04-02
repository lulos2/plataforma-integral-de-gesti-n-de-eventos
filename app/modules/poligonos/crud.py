from __future__ import annotations

from datetime import datetime
from typing import Any

from shapely.geometry import Polygon
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from geoalchemy2.shape import from_shape

from app.modules.events.models import Evento, TipoEvento
from app.modules.events.models_domain import EventoVideoseguridad
from app.modules.poligonos.models import Poligono


def _point_lat_lon(raw: Any) -> tuple[float, float]:
    if hasattr(raw, "latitud") and hasattr(raw, "longitud"):
        return float(raw.latitud), float(raw.longitud)
    if isinstance(raw, dict):
        return float(raw["latitud"]), float(raw["longitud"])
    raise ValueError("formato de punto invalido")


def _normalize_points(points: list[Any]) -> list[dict[str, float]]:
    normalized: list[dict[str, float]] = []
    for point in points:
        lat, lon = _point_lat_lon(point)
        normalized.append({"latitud": lat, "longitud": lon})
    return normalized


def _build_polygon(points: list[dict[str, float]]) -> Polygon:
    coords = [(p["longitud"], p["latitud"]) for p in points]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    polygon = Polygon(coords)
    if polygon.area == 0:
        raise ValueError("los puntos no forman un poligono con area")
    if not polygon.is_valid:
        raise ValueError("los puntos forman un poligono invalido (autointerseccion o geometria incorrecta)")
    return polygon


def _compute_area_m2(db: Session, polygon: Polygon) -> float:
    # Accurate geodesic area on WGS84 using PostGIS geography.
    if db.bind and db.bind.dialect.name == "postgresql":
        ewkt = f"SRID=4326;{polygon.wkt}"
        area = db.execute(
            text("SELECT ST_Area(ST_GeogFromText(:ewkt))"),
            {"ewkt": ewkt},
        ).scalar()
        return float(area or 0.0)

    # Fallback approximation for non-PostgreSQL engines.
    return float(abs(polygon.area) * (111_320.0**2))


def crear_poligono(db: Session, *, data) -> Poligono:
    existing = db.query(Poligono).filter(Poligono.nombre == data.nombre).first()
    if existing:
        raise ValueError("ya existe un poligono con ese nombre")

    puntos = _normalize_points(data.puntos)
    polygon = _build_polygon(puntos)
    area_m2 = _compute_area_m2(db, polygon)

    poligono = Poligono(
        nombre=data.nombre.strip(),
        descripcion=data.descripcion,
        puntos=puntos,
        area_m2=area_m2,
        geometria=from_shape(polygon, srid=4326),
    )
    db.add(poligono)
    db.commit()
    db.refresh(poligono)
    return poligono


def listar_poligonos(db: Session) -> list[Poligono]:
    return db.query(Poligono).order_by(Poligono.nombre.asc()).all()


def obtener_poligono(db: Session, *, poligono_id: int) -> Poligono | None:
    return db.query(Poligono).filter(Poligono.id == poligono_id).first()


def actualizar_poligono(db: Session, *, poligono_id: int, data) -> Poligono | None:
    poligono = obtener_poligono(db, poligono_id=poligono_id)
    if not poligono:
        return None

    payload = data.model_dump(exclude_unset=True)
    if "nombre" in payload:
        nombre = payload["nombre"].strip()
        if nombre != poligono.nombre:
            duplicate = db.query(Poligono).filter(Poligono.nombre == nombre, Poligono.id != poligono.id).first()
            if duplicate:
                raise ValueError("ya existe un poligono con ese nombre")
            poligono.nombre = nombre

    if "descripcion" in payload:
        poligono.descripcion = payload["descripcion"]
    if "puntos" in payload:
        puntos = _normalize_points(payload["puntos"])
        polygon = _build_polygon(puntos)
        poligono.puntos = puntos
        poligono.geometria = from_shape(polygon, srid=4326)
        poligono.area_m2 = _compute_area_m2(db, polygon)

    db.add(poligono)
    db.commit()
    db.refresh(poligono)
    return poligono


def eliminar_poligono(db: Session, *, poligono_id: int) -> bool:
    poligono = obtener_poligono(db, poligono_id=poligono_id)
    if not poligono:
        return False
    db.delete(poligono)
    db.commit()
    return True


def listar_eventos_en_poligono(
    db: Session,
    *,
    poligono_id: int,
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
) -> list[Evento]:
    q = (
        db.query(Evento)
        .options(joinedload(Evento.tipo_evento))
        .join(Poligono, Poligono.id == poligono_id)
        .filter(func.ST_Covers(Poligono.geometria, Evento.ubicacion))
    )

    if area:
        q = q.join(Evento.tipo_evento).filter(TipoEvento.area == area)
    if tipo_evento_id is not None:
        q = q.filter(Evento.tipo_evento_id == tipo_evento_id)
    if servicio_actuante_id is not None:
        q = q.join(EventoVideoseguridad, EventoVideoseguridad.evento_id == Evento.id).filter(
            EventoVideoseguridad.servicio_actuante_id == servicio_actuante_id
        )
    if fecha_desde is not None:
        q = q.filter(func.coalesce(Evento.fecha_ocurrencia, Evento.fecha_creacion) >= fecha_desde)
    if fecha_hasta is not None:
        q = q.filter(func.coalesce(Evento.fecha_ocurrencia, Evento.fecha_creacion) <= fecha_hasta)

    return q.order_by(Evento.fecha_creacion.desc()).all()
