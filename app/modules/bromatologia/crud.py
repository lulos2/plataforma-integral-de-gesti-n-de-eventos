from sqlalchemy.orm import Session

from app.modules.events import crud as events_crud
from app.modules.events.models_domain import Comercio, EventoBromatologia
from app.modules.bromatologia.schemas import EventoBromatologiaCreate


def crear_evento_bromatologia(
    db: Session,
    *,
    tipo_nombre: str,
    data: EventoBromatologiaCreate,
    actor_usuario_id: int,
):
    tipo = events_crud.obtener_tipo_evento_por_area_nombre(db, area="bromatologia", nombre=tipo_nombre)
    if not tipo:
        raise ValueError("tipo_evento invalido para bromatologia")

    if data.comercio_id is not None:
        comercio = db.query(Comercio).filter(Comercio.id == data.comercio_id).first()
        if not comercio:
            raise ValueError("comercio_id invalido")

    with db.begin():
        evento, _ = events_crud.crear_evento_base(
            db,
            tipo_evento_id=tipo.id,
            data=data,
            actor_usuario_id=actor_usuario_id,
        )
        db.add(
            EventoBromatologia(
                evento_id=evento.id,
                comercio_id=data.comercio_id,
                acta_numero=data.acta_numero,
                resultado=data.resultado,
                observaciones=data.observaciones,
            )
        )
        events_crud._crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="create")

    db.refresh(evento)
    return evento
