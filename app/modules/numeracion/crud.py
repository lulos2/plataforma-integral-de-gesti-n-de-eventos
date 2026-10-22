from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.serialization import ARGENTINA_TZ
from app.modules.events import crud as events_crud
from app.modules.events.models import Evento, NumeracionArea


def listar_numeraciones(db: Session, *, areas: list[str]) -> list[NumeracionArea]:
    return (
        db.query(NumeracionArea)
        .filter(NumeracionArea.area.in_(areas))
        .order_by(NumeracionArea.area.asc())
        .all()
    )


def obtener_numeracion(db: Session, *, area: str) -> NumeracionArea | None:
    return db.query(NumeracionArea).filter(NumeracionArea.area == area).first()


def inicializar_numeracion(
    db: Session, *, area: str, ultimo_numero: int, actor_usuario_id: int
) -> NumeracionArea | None:
    """Configura el contador del area. Solo se puede una vez, aunque lleguen dos pedidos a la vez."""
    try:
        contador = events_crud.bloquear_numeracion(db, area)
        if contador is None:
            return None
        if contador.inicializada:
            raise events_crud.NumeracionYaConfiguradaError(
                f"La numeracion del area {area} ya fue configurada y no se puede cambiar"
            )

        # No puede quedar por debajo de un numero que ya existe en el area (se repetiria).
        maximo = db.query(func.max(Evento.numero_evento)).filter(Evento.area == area).scalar() or 0
        if ultimo_numero < maximo:
            raise ValueError(
                f"ya existen eventos de {area} hasta el numero {maximo}: informar ese numero o uno mayor"
            )

        actor = events_crud._obtener_actor(db, actor_usuario_id)
        contador.inicializada = True
        contador.ultimo_informado = ultimo_numero
        contador.ultimo_numero = ultimo_numero
        contador.configurado_por_id = actor.id
        contador.configurado_por_nombre = actor.nombre
        contador.configurado_por_apellido = actor.apellido
        contador.fecha_configuracion = datetime.now(ARGENTINA_TZ)
        db.add(contador)
        events_crud._crear_audit(
            db,
            numeracion_area=area,
            actor_usuario_id=actor_usuario_id,
            accion="inicializar_numeracion",
            detalle={"ultimo_informado": ultimo_numero, "siguiente_numero": ultimo_numero + 1},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(contador)
    return contador
