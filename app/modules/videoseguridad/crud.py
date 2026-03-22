from __future__ import annotations

import re

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.modules.events import crud as events_crud
from app.modules.events.models_domain import EventoVideoseguridad, ServicioActuante, Camara
from app.modules.videoseguridad.schemas import EventoVideoseguridadCreate


_CAMARA_RE = re.compile(r"^\s*camara\s+(\d+)\s*$", flags=re.IGNORECASE)


def _resolve_servicio_actuante_id(
    db: Session,
    *,
    servicio_actuante_id: int | None,
    servicio_actuante: str | None,
) -> int:
    if servicio_actuante_id is not None and servicio_actuante is not None and servicio_actuante.strip() != "":
        raise ValueError("enviar solo uno: servicio_actuante_id o servicio_actuante")

    if servicio_actuante_id is not None:
        svc = db.query(ServicioActuante).filter(ServicioActuante.id == servicio_actuante_id).first()
        if not svc:
            raise ValueError("servicio_actuante_id invalido")
        return svc.id

    name = (servicio_actuante or "").strip()
    if name != "":
        svc = db.query(ServicioActuante).filter(func.lower(ServicioActuante.nombre) == name.lower()).first()
        if svc:
            return svc.id

        allowed = [row[0] for row in db.query(ServicioActuante.nombre).order_by(ServicioActuante.nombre.asc()).all()]
        if allowed:
            raise ValueError(f"servicio_actuante invalido. Valores: {', '.join(allowed)}")
        raise ValueError("servicio_actuante invalido")

    # Si no se envía servicio, usamos el default "indefinido".
    default_svc = db.query(ServicioActuante).filter(func.lower(ServicioActuante.nombre) == "indefinido").first()
    if default_svc:
        return default_svc.id

    raise ValueError("falta configurar servicio_actuante 'indefinido'")


def _resolve_camara_id(db: Session, *, camara_id: int | None, camara: str | None) -> int | None:
    if camara_id is not None and camara is not None and camara.strip() != "":
        # Avoid ambiguous inputs.
        raise ValueError("enviar solo uno: camara_id o camara")

    if camara_id is not None:
        return camara_id

    if camara is None:
        return None

    raw = camara.strip()
    if raw == "":
        return None

    # Match by codigo. Accept a couple of common variants for convenience.
    candidates: list[str] = [raw]
    m = _CAMARA_RE.match(raw)
    if m:
        n = m.group(1)
        candidates.extend([f"camara {n}", n, f"camara_{n}", f"camara-{n}"])

    lowered = {c.strip().lower() for c in candidates if c.strip() != ""}
    for code in candidates:
        code = code.strip()
        if not code:
            continue
        cam = db.query(Camara).filter(Camara.codigo == code).first()
        if cam:
            return cam.id

    cam = db.query(Camara).filter(func.lower(Camara.codigo).in_(sorted(lowered))).first()
    if cam:
        return cam.id

    return None


def crear_evento_videoseguridad(
    db: Session,
    *,
    tipo_nombre: str,
    data: EventoVideoseguridadCreate,
    actor_usuario_id: int,
):
    tipo = events_crud.obtener_tipo_evento_por_area_nombre(db, area="videoseguridad", nombre=tipo_nombre)
    if not tipo:
        raise ValueError("tipo_evento invalido para videoseguridad")

    resolved_servicio_actuante_id = _resolve_servicio_actuante_id(
        db,
        servicio_actuante_id=data.servicio_actuante_id,
        servicio_actuante=getattr(data, "servicio_actuante", None),
    )

    resolved_camara_id = _resolve_camara_id(db, camara_id=data.camara_id, camara=getattr(data, "camara", None))

    try:
        evento, _ = events_crud.crear_evento_base(
            db,
            tipo_evento_id=tipo.id,
            data=data,
            actor_usuario_id=actor_usuario_id,
        )
        db.add(
            EventoVideoseguridad(
                evento_id=evento.id,
                servicio_actuante_id=resolved_servicio_actuante_id,
                camara_id=resolved_camara_id,
                prioridad=data.prioridad,
            )
        )
        events_crud._crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="create")
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(evento)
    return evento
