from sqlalchemy.orm import Session

from app.modules.events import crud as events_crud
from app.modules.events.models_domain import EventoZoonosis
from app.modules.zoonosis.schemas import EventoZoonosisCreate, EventoZoonosisUpdate


def crear_evento_zoonosis(
    db: Session,
    *,
    tipo_nombre: str,
    data: EventoZoonosisCreate,
    actor_usuario_id: int,
):
    tipo = events_crud.obtener_tipo_evento_por_area_nombre(db, area="zoonosis", nombre=tipo_nombre)
    if not tipo:
        raise ValueError("tipo_evento invalido para zoonosis")

    try:
        evento, _ = events_crud.crear_evento_base(
            db,
            tipo_evento_id=tipo.id,
            data=data,
            actor_usuario_id=actor_usuario_id,
        )
        db.add(
            EventoZoonosis(
                evento_id=evento.id,
                especie=data.especie,
                propietario=data.propietario,
                observaciones=data.observaciones,
                requiere_control_antirrabico=data.requiere_control_antirrabico,
            )
        )
        events_crud._crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="create")
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(evento)
    return evento


def actualizar_evento_zoonosis(
    db: Session,
    *,
    evento_id: int,
    data: EventoZoonosisUpdate,
    actor_usuario_id: int,
):
    registro = db.query(EventoZoonosis).filter(EventoZoonosis.evento_id == evento_id).first()
    if not registro:
        return None

    detalle: dict = {}

    for campo in ("especie", "propietario", "observaciones", "requiere_control_antirrabico"):
        nuevo = getattr(data, campo)
        if nuevo is not None and nuevo != getattr(registro, campo):
            detalle[campo] = {"from": getattr(registro, campo), "to": nuevo}
            setattr(registro, campo, nuevo)

    db.add(registro)
    db.commit()
    db.refresh(registro)

    if detalle:
        events_crud._crear_audit(db, evento_id=evento_id, actor_usuario_id=actor_usuario_id, accion="update", detalle=detalle)
        db.commit()

    return registro
