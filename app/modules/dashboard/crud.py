from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.core.serialization import ARGENTINA_TZ
from app.modules.events.models import Evento, TipoEvento
from app.modules.events.models_domain import EventoVideoseguridad

DIAS_EVOLUCION = 30
ULTIMOS_EVENTOS = 5
# Zona usada para agrupar por dia dentro de la base (Argentina no tiene horario de verano,
# equivale al GMT-3 fijo que usa el resto de la API).
ZONA_SQL = "America/Argentina/Buenos_Aires"


def obtener_resumen(db: Session, *, area: str | None) -> dict:
    # Todos los periodos son calendario en hora argentina y terminan en el momento de la consulta.
    ahora = datetime.now(ARGENTINA_TZ).replace(microsecond=0)
    inicio_dia = ahora.replace(hour=0, minute=0, second=0)
    inicio_semana = inicio_dia - timedelta(days=inicio_dia.weekday())
    inicio_mes = inicio_dia.replace(day=1)
    inicio_30_dias = inicio_dia - timedelta(days=DIAS_EVOLUCION - 1)

    fecha = Evento.fecha_ocurrencia

    def en_periodo(desde: datetime):
        return and_(fecha >= desde, fecha <= ahora)

    q = db.query(Evento)
    if area:
        q = q.join(Evento.tipo_evento).filter(TipoEvento.area == area)

    abiertos, hoy, semana, mes = q.with_entities(
        func.count(Evento.id).filter(Evento.estado == "abierto"),
        func.count(Evento.id).filter(en_periodo(inicio_dia)),
        func.count(Evento.id).filter(en_periodo(inicio_semana)),
        func.count(Evento.id).filter(en_periodo(inicio_mes)),
    ).one()

    # Evolucion diaria: se agrupa por dia argentino y se completan con cero los dias sin eventos.
    dia_local = func.date(func.timezone(ZONA_SQL, fecha))
    q_dias = db.query(dia_local, func.count(Evento.id)).filter(en_periodo(inicio_30_dias))
    if area:
        q_dias = q_dias.join(Evento.tipo_evento).filter(TipoEvento.area == area)
    por_dia: dict[date, int] = {d: c for d, c in q_dias.group_by(dia_local).all()}
    primer_dia = inicio_30_dias.date()
    evolucion = [
        {"fecha": d, "cantidad": por_dia.get(d, 0)}
        for d in (primer_dia + timedelta(days=i) for i in range(DIAS_EVOLUCION))
    ]

    # Distribucion por tipo en los mismos 30 dias (tambien los tipos sin eventos, con cero).
    cantidad = func.count(Evento.id)
    q_tipos = (
        db.query(TipoEvento.area, TipoEvento.nombre, cantidad)
        .outerjoin(Evento, and_(Evento.tipo_evento_id == TipoEvento.id, en_periodo(inicio_30_dias)))
    )
    if area:
        q_tipos = q_tipos.filter(TipoEvento.area == area)
    tipos = (
        q_tipos.group_by(TipoEvento.area, TipoEvento.nombre)
        .order_by(cantidad.desc(), TipoEvento.area.asc(), TipoEvento.nombre.asc())
        .all()
    )

    # Ultimos eventos por fecha de ocurrencia, desempatando por ID. Como el resto del resumen,
    # llega hasta el momento de la consulta (no cuenta fechas futuras ni eventos viejos sin fecha).
    q_ultimos = db.query(Evento).options(
        joinedload(Evento.tipo_evento),
        joinedload(Evento.videoseguridad).joinedload(EventoVideoseguridad.servicio_actuante),
    ).filter(fecha <= ahora)
    if area:
        q_ultimos = q_ultimos.join(Evento.tipo_evento).filter(TipoEvento.area == area)
    ultimos = q_ultimos.order_by(fecha.desc(), Evento.id.desc()).limit(ULTIMOS_EVENTOS).all()

    return {
        "area": area,
        "generado_en": ahora,
        "periodos": {
            "hoy": {"desde": inicio_dia, "hasta": ahora},
            "semana": {"desde": inicio_semana, "hasta": ahora},
            "mes": {"desde": inicio_mes, "hasta": ahora},
            "ultimos_30_dias": {"desde": inicio_30_dias, "hasta": ahora},
        },
        "eventos_mes": mes,
        "eventos_semana": semana,
        "eventos_hoy": hoy,
        "eventos_abiertos": abiertos,
        "evolucion_diaria": evolucion,
        "distribucion_por_tipo": [
            {"area": f_area, "tipo_evento": f_nombre, "cantidad": f_cantidad}
            for f_area, f_nombre, f_cantidad in tipos
        ],
        "ultimos_eventos": [
            {
                "id": e.id,
                "numero_evento": e.numero_evento,
                "descripcion": e.descripcion,
                "area": e.tipo_evento.area,
                "tipo_evento": e.tipo_evento.nombre,
                "fecha_ocurrencia": e.fecha_ocurrencia,
                "direccion": e.direccion,
                "servicio_actuante": (
                    e.videoseguridad.servicio_actuante.nombre
                    if e.videoseguridad and e.videoseguridad.servicio_actuante
                    else None
                ),
                "estado": e.estado,
            }
            for e in ultimos
        ],
    }
