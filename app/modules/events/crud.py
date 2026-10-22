from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.core.serialization import ARGENTINA_TZ, to_argentina_iso
from app.modules.events.models import Evento, EventoAudit, NumeracionArea, TipoEvento
from app.modules.events.models_domain import EventoIntervencion, EventoVideoseguridad, EventoZoonosis, ServicioActuante
from app.modules.users.models import Usuario


class EventoAnuladoError(Exception):
    """El evento esta anulado: se conserva pero ya no admite cambios."""


class NumeracionNoConfiguradaError(Exception):
    """La numeracion del area todavia no fue inicializada: no se pueden crear eventos."""


class NumeracionYaConfiguradaError(Exception):
    """La numeracion del area ya fue inicializada y no puede configurarse otra vez."""


class _EventoBaseData(Protocol):
    descripcion: str | None
    fuente: str
    estado: str
    fecha_ocurrencia: datetime
    latitud: float
    longitud: float
    turno: str | None
    direccion: str | None
    origen: str | None
    recibio_nombre: str | None
    recibio_funcion: str | None
    observaciones_cierre: str | None


def _limpiar_texto(valor: str | None) -> str | None:
    return (valor or "").strip() or None


def _patron_like(texto: str) -> str:
    escapado = texto.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def _a_json(valor):
    # El detalle de auditoria se guarda como JSON: las fechas se pasan a texto en hora argentina.
    if isinstance(valor, datetime):
        return to_argentina_iso(valor)
    if isinstance(valor, dict):
        return {k: _a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_a_json(v) for v in valor]
    return valor


def _obtener_actor(db: Session, actor_usuario_id: int) -> Usuario:
    actor = db.query(Usuario).filter(Usuario.id == actor_usuario_id).first()
    if not actor:
        raise ValueError("usuario invalido")
    return actor


def _crear_audit(
    db: Session,
    *,
    evento_id: int | None = None,
    actor_usuario_id: int,
    accion: str,
    detalle: dict | None = None,
    numeracion_area: str | None = None,
):
    # No hace commit: la auditoria se guarda en la misma transaccion que el cambio que registra.
    # Si la operacion no es sobre un evento (inicializar la numeracion), va con su area en numeracion_area.
    actor = _obtener_actor(db, actor_usuario_id)
    db.add(
        EventoAudit(
            evento_id=evento_id,
            numeracion_area=numeracion_area,
            actor_usuario_id=actor_usuario_id,
            actor_area=actor.area,
            actor_turno=actor.turno,
            accion=accion,
            detalle=_a_json(detalle),
        )
    )


def bloquear_numeracion(db: Session, area: str) -> NumeracionArea | None:
    # Bloquea la fila del contador hasta el commit: dos pedidos simultaneos del mismo area hacen cola.
    return (
        db.query(NumeracionArea)
        .filter(NumeracionArea.area == area)
        .populate_existing()
        .with_for_update()
        .first()
    )


def asignar_siguiente_numero(db: Session, area: str) -> int:
    contador = bloquear_numeracion(db, area)
    if contador is None or not contador.inicializada:
        raise NumeracionNoConfiguradaError(
            f"La numeracion del area {area} no esta configurada: el administrador del area debe inicializarla"
        )
    contador.ultimo_numero += 1
    return contador.ultimo_numero


def verificar_no_anulado(evento: Evento) -> None:
    if evento.estado == "anulado":
        raise EventoAnuladoError("El evento esta anulado y no admite cambios")


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

    actor = _obtener_actor(db, actor_usuario_id)
    cerrado = data.estado == "cerrado"
    observaciones_cierre = _limpiar_texto(data.observaciones_cierre)
    if cerrado and not observaciones_cierre:
        raise ValueError("observaciones_cierre es obligatoria para cerrar un evento")
    if not cerrado and observaciones_cierre:
        raise ValueError("observaciones_cierre solo se puede indicar en un evento cerrado")

    # El numero se toma recien despues de validar todo, para tener el contador bloqueado el menor tiempo posible.
    numero_evento = asignar_siguiente_numero(db, tipo.area)

    evento = Evento(
        tipo_evento_id=tipo_evento_id,
        area=tipo.area,
        numero_evento=numero_evento,
        descripcion=data.descripcion,
        fuente=data.fuente,
        estado=data.estado,
        fecha_ocurrencia=data.fecha_ocurrencia,
        latitud=data.latitud,
        longitud=data.longitud,
        ubicacion=point,
        turno=data.turno,
        direccion=data.direccion,
        origen=data.origen,
        recibio_nombre=data.recibio_nombre,
        recibio_funcion=data.recibio_funcion,
        usuario_id=actor_usuario_id,
        fecha_cierre=datetime.now(ARGENTINA_TZ) if cerrado else None,
        cerrado_por_id=actor_usuario_id if cerrado else None,
        cierre_origen="sistema" if cerrado else None,
        cierre_nombre=actor.nombre if cerrado else None,
        cierre_apellido=actor.apellido if cerrado else None,
        observaciones_cierre=observaciones_cierre,
    )

    db.add(evento)
    db.flush()  # assign evento.id without committing
    _crear_audit(db, evento_id=evento.id, actor_usuario_id=actor_usuario_id, accion="create")
    return evento, tipo


def obtener_eventos(
    db: Session,
    *,
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    estado: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    limite: int | None = None,
    turno: str | None = None,
    direccion: str | None = None,
    especie: str | None = None,
    buscar: str | None = None,
):

    q = db.query(Evento).options(
        joinedload(Evento.tipo_evento),
        joinedload(Evento.videoseguridad).joinedload(EventoVideoseguridad.servicio_actuante),
        joinedload(Evento.videoseguridad).joinedload(EventoVideoseguridad.camara),
        joinedload(Evento.zoonosis),
    )

    if area:
        q = q.join(Evento.tipo_evento).filter(TipoEvento.area == area)

    if tipo_evento_id:
        q = q.filter(Evento.tipo_evento_id == tipo_evento_id)

    if servicio_actuante_id:
        q = q.join(EventoVideoseguridad, EventoVideoseguridad.evento_id == Evento.id).filter(
            EventoVideoseguridad.servicio_actuante_id == servicio_actuante_id
        )

    if estado:
        q = q.filter(Evento.estado == estado)
    else:
        # Los anulados solo aparecen si se piden explicitamente con estado=anulado.
        q = q.filter(Evento.estado != "anulado")

    if fecha_desde:
        q = q.filter(Evento.fecha_ocurrencia >= fecha_desde)

    if fecha_hasta:
        q = q.filter(Evento.fecha_ocurrencia <= fecha_hasta)

    if turno and turno.strip():
        q = q.filter(func.lower(Evento.turno) == turno.strip().lower())

    if direccion and direccion.strip():
        q = q.filter(Evento.direccion.ilike(_patron_like(direccion), escape="\\"))

    if especie and especie.strip():
        q = q.join(EventoZoonosis, EventoZoonosis.evento_id == Evento.id).filter(
            func.lower(EventoZoonosis.especie) == especie.strip().lower()
        )

    if buscar and buscar.strip():
        patron = _patron_like(buscar)
        criterios = [
            Evento.descripcion.ilike(patron, escape="\\"),
            Evento.direccion.ilike(patron, escape="\\"),
        ]
        if buscar.strip().isdigit():
            criterios.append(Evento.numero_evento == int(buscar.strip()))
        q = q.filter(or_(*criterios))

    q = q.order_by(Evento.fecha_creacion.desc())
    if limite:
        q = q.limit(limite)
    return q.all()


def obtener_puntos_mapa(
    db: Session,
    *,
    area: str | None = None,
    tipo_evento_id: int | None = None,
    servicio_actuante_id: int | None = None,
    estado: str | None = None,
    turno: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
) -> list[dict]:
    # Consulta liviana (solo lo que necesita el mapa). La fecha de un evento es siempre su
    # fecha_ocurrencia (la de carga no la reemplaza).
    fecha_evento = Evento.fecha_ocurrencia

    q = db.query(
        Evento.id,
        Evento.numero_evento,
        Evento.latitud,
        Evento.longitud,
        Evento.estado,
        fecha_evento.label("fecha"),
        TipoEvento.area,
        TipoEvento.nombre,
    ).join(TipoEvento, TipoEvento.id == Evento.tipo_evento_id)

    if area:
        q = q.filter(TipoEvento.area == area)
    if tipo_evento_id:
        q = q.filter(Evento.tipo_evento_id == tipo_evento_id)
    if servicio_actuante_id:
        q = q.join(EventoVideoseguridad, EventoVideoseguridad.evento_id == Evento.id).filter(
            EventoVideoseguridad.servicio_actuante_id == servicio_actuante_id
        )
    if estado:
        q = q.filter(Evento.estado == estado)
    else:
        q = q.filter(Evento.estado != "anulado")
    if turno and turno.strip():
        q = q.filter(func.lower(Evento.turno) == turno.strip().lower())
    if fecha_desde:
        q = q.filter(fecha_evento >= fecha_desde)
    if fecha_hasta:
        q = q.filter(fecha_evento <= fecha_hasta)

    return [
        {
            "id": f_id,
            "numero_evento": f_numero,
            "latitud": f_lat,
            "longitud": f_lon,
            "estado": f_estado,
            "fecha": f_fecha,
            "area": f_area,
            "tipo_evento": f_tipo,
        }
        for f_id, f_numero, f_lat, f_lon, f_estado, f_fecha, f_area, f_tipo in q.order_by(fecha_evento.desc()).all()
    ]


def obtener_estadisticas(db: Session, *, area: str | None = None) -> dict:
    # Periodos calendario en hora argentina: dia de hoy, semana desde el lunes, mes en curso.
    inicio_dia = datetime.now(ARGENTINA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = inicio_dia - timedelta(days=inicio_dia.weekday())
    inicio_mes = inicio_dia.replace(day=1)
    fin_dia = inicio_dia + timedelta(days=1)
    fin_semana = inicio_semana + timedelta(days=7)
    fin_mes = (inicio_mes + timedelta(days=32)).replace(day=1)

    # Los eventos viejos sin fecha_ocurrencia cuentan en los totales pero no en hoy/semana/mes.
    fecha_evento = Evento.fecha_ocurrencia

    # Los eventos anulados no cuentan en ningun indicador.
    q = db.query(Evento).filter(Evento.estado != "anulado")
    if area:
        q = q.join(Evento.tipo_evento).filter(TipoEvento.area == area)

    total, abiertos, cerrados, hoy, semana, mes = q.with_entities(
        func.count(Evento.id),
        func.count(Evento.id).filter(Evento.estado == "abierto"),
        func.count(Evento.id).filter(Evento.estado == "cerrado"),
        func.count(Evento.id).filter(and_(fecha_evento >= inicio_dia, fecha_evento < fin_dia)),
        func.count(Evento.id).filter(and_(fecha_evento >= inicio_semana, fecha_evento < fin_semana)),
        func.count(Evento.id).filter(and_(fecha_evento >= inicio_mes, fecha_evento < fin_mes)),
    ).one()

    cantidad = func.count(Evento.id)
    q_tipos = db.query(TipoEvento.area, TipoEvento.nombre, cantidad).join(
        Evento, Evento.tipo_evento_id == TipoEvento.id
    ).filter(Evento.estado != "anulado")
    if area:
        q_tipos = q_tipos.filter(TipoEvento.area == area)
    filas = (
        q_tipos.group_by(TipoEvento.area, TipoEvento.nombre)
        .order_by(cantidad.desc(), TipoEvento.nombre.asc())
        .all()
    )

    return {
        "area": area,
        "total": total,
        "abiertos": abiertos,
        "cerrados": cerrados,
        "hoy": hoy,
        "semana": semana,
        "mes": mes,
        "por_tipo": [
            {"area": f_area, "tipo_evento": f_nombre, "cantidad": f_cantidad}
            for f_area, f_nombre, f_cantidad in filas
        ],
    }


def obtener_evento(db: Session, evento_id: int) -> Evento | None:

    return (
        db.query(Evento)
        .options(
            joinedload(Evento.tipo_evento),
            joinedload(Evento.videoseguridad).joinedload(EventoVideoseguridad.servicio_actuante),
            joinedload(Evento.videoseguridad).joinedload(EventoVideoseguridad.camara),
            joinedload(Evento.zoonosis),
        )
        .filter(Evento.id == evento_id)
        .first()
    )


def crear_intervencion(db: Session, *, evento_id: int, data, actor_usuario_id: int):
    evento = db.query(Evento).filter(Evento.id == evento_id).first()
    if not evento:
        return None
    verificar_no_anulado(evento)

    servicio = db.query(ServicioActuante).filter(ServicioActuante.id == data.servicio_actuante_id).first()
    if not servicio:
        raise ValueError("servicio_actuante_id invalido")

    intervencion = EventoIntervencion(
        evento_id=evento_id,
        servicio_actuante_id=data.servicio_actuante_id,
        actor_usuario_id=actor_usuario_id,
        asignado_en=data.asignado_en,
        arribo_en=data.arribo_en,
        cerrado_en=data.cerrado_en,
        notas=data.notas,
        resultado=data.resultado,
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


def _bloquear_evento(db: Session, evento_id: int) -> Evento | None:
    # Bloquea la fila hasta el commit, para que dos pedidos simultaneos sobre el mismo evento no se pisen.
    return db.query(Evento).filter(Evento.id == evento_id).populate_existing().with_for_update().first()


def _cierre_actual(evento: Evento) -> dict:
    return {
        "origen": evento.cierre_origen,
        "usuario_id": evento.cerrado_por_id,
        "nombre": evento.cierre_nombre,
        "apellido": evento.cierre_apellido,
        "fecha": evento.fecha_cierre,
        "observaciones": evento.observaciones_cierre,
    }


def actualizar_evento(db: Session, evento_id: int, data, *, actor_usuario_id: int):
    try:
        evento = _bloquear_evento(db, evento_id)
        if not evento:
            return None
        verificar_no_anulado(evento)
        actor = _obtener_actor(db, actor_usuario_id)

        # Se valida todo lo del cierre antes de modificar nada.
        estado_antes = evento.estado
        estado_nuevo = data.estado if data.estado is not None else estado_antes
        observaciones_cierre = _limpiar_texto(data.observaciones_cierre)
        cierra = estado_nuevo == "cerrado" and estado_antes != "cerrado"

        if estado_antes == "cerrado" and estado_nuevo == "abierto":
            raise ValueError("para reabrir un evento cerrado usar POST /eventos/{id}/reabrir")
        if cierra and not observaciones_cierre:
            raise ValueError("observaciones_cierre es obligatoria para cerrar un evento")
        if observaciones_cierre and estado_nuevo != "cerrado":
            raise ValueError("observaciones_cierre solo se puede indicar en un evento cerrado")

        detalle = {}

        for campo in (
            "descripcion",
            "fuente",
            "estado",
            "fecha_ocurrencia",
            "turno",
            "direccion",
            "origen",
            "recibio_nombre",
            "recibio_funcion",
        ):
            nuevo = getattr(data, campo)
            if nuevo is not None and nuevo != getattr(evento, campo):
                detalle[campo] = {"from": getattr(evento, campo), "to": nuevo}
                setattr(evento, campo, nuevo)

        if cierra:
            evento.fecha_cierre = datetime.now(ARGENTINA_TZ)
            evento.cerrado_por_id = actor.id
            evento.cierre_origen = "sistema"
            evento.cierre_nombre = actor.nombre
            evento.cierre_apellido = actor.apellido
            evento.observaciones_cierre = observaciones_cierre
            detalle["cierre"] = {"from": None, "to": _cierre_actual(evento)}
        elif observaciones_cierre and observaciones_cierre != evento.observaciones_cierre:
            # Evento que ya estaba cerrado: se corrige solo el texto. El responsable y la fecha
            # del cierre original no cambian.
            detalle["observaciones_cierre"] = {"from": evento.observaciones_cierre, "to": observaciones_cierre}
            evento.observaciones_cierre = observaciones_cierre

        if data.latitud is not None or data.longitud is not None:
            nueva_lat = evento.latitud if data.latitud is None else data.latitud
            nueva_lon = evento.longitud if data.longitud is None else data.longitud
            if nueva_lat != evento.latitud or nueva_lon != evento.longitud:
                detalle["ubicacion"] = {"from": [evento.latitud, evento.longitud], "to": [nueva_lat, nueva_lon]}
                evento.latitud = nueva_lat
                evento.longitud = nueva_lon
                evento.ubicacion = from_shape(Point(nueva_lon, nueva_lat), srid=4326)

        db.add(evento)
        if detalle:
            # El cambio y su auditoria se confirman juntos: si una falla, no se guarda ninguna.
            _crear_audit(
                db,
                evento_id=evento.id,
                actor_usuario_id=actor_usuario_id,
                accion="cerrar" if cierra else "update",
                detalle=detalle,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return obtener_evento(db, evento_id)


def anular_evento(db: Session, evento_id: int, *, motivo: str, actor_usuario_id: int):
    """Anula el evento (no se borra): conserva numero, datos e historial."""
    try:
        evento = _bloquear_evento(db, evento_id)
        if not evento:
            return None
        if evento.estado == "anulado":
            raise ValueError("el evento ya esta anulado")
        motivo = _limpiar_texto(motivo)
        if not motivo:
            raise ValueError("el motivo es obligatorio")
        actor = _obtener_actor(db, actor_usuario_id)

        estado_anterior = evento.estado
        evento.estado = "anulado"
        evento.fecha_anulacion = datetime.now(ARGENTINA_TZ)
        evento.anulado_por_id = actor.id
        evento.anulado_por_nombre = actor.nombre
        evento.anulado_por_apellido = actor.apellido
        evento.motivo_anulacion = motivo
        db.add(evento)
        _crear_audit(
            db,
            evento_id=evento.id,
            actor_usuario_id=actor_usuario_id,
            accion="anular",
            detalle={"estado": {"from": estado_anterior, "to": "anulado"}, "motivo": motivo},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return obtener_evento(db, evento_id)


def reabrir_evento(db: Session, evento_id: int, *, motivo: str, actor_usuario_id: int):
    """Reabre un evento cerrado. El cierre anterior no se pierde: queda en el historial."""
    try:
        evento = _bloquear_evento(db, evento_id)
        if not evento:
            return None
        verificar_no_anulado(evento)
        if evento.estado != "cerrado":
            raise ValueError("solo se puede reabrir un evento cerrado")
        motivo = _limpiar_texto(motivo)
        if not motivo:
            raise ValueError("el motivo es obligatorio")

        cierre_anterior = _cierre_actual(evento)
        evento.estado = "abierto"
        evento.fecha_cierre = None
        evento.cerrado_por_id = None
        evento.cierre_origen = None
        evento.cierre_nombre = None
        evento.cierre_apellido = None
        evento.observaciones_cierre = None
        db.add(evento)
        _crear_audit(
            db,
            evento_id=evento.id,
            actor_usuario_id=actor_usuario_id,
            accion="reabrir",
            detalle={
                "estado": {"from": "cerrado", "to": "abierto"},
                "motivo": motivo,
                "cierre_anterior": cierre_anterior,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return obtener_evento(db, evento_id)


def listar_historial(db: Session, *, evento_id: int) -> list[EventoAudit]:
    return (
        db.query(EventoAudit)
        .options(joinedload(EventoAudit.actor_usuario))
        .filter(EventoAudit.evento_id == evento_id)
        .order_by(EventoAudit.fecha.asc(), EventoAudit.id.asc())
        .all()
    )


def listar_tipos_evento(db: Session, *, area: str | None = None):
    q = db.query(TipoEvento)
    if area:
        q = q.filter(TipoEvento.area == area)
    return q.order_by(TipoEvento.area.asc(), TipoEvento.nombre.asc()).all()
