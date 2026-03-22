from sqlalchemy.orm import Session

from app.modules.events import crud as events_crud
from app.modules.events.models_domain import EventoZoonosis
from app.modules.zoonosis.schemas import EventoZoonosisCreate


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

    with db.begin():
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
                observaciones=data.observaciones,
                requiere_control_antirrabico=data.requiere_control_antirrabico,
            )
        )
        events_crud._crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="create")

    db.refresh(evento)
    return evento
