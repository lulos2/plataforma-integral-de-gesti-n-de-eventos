from app.modules.events.schemas import EventoResponse


def to_evento_response(evento) -> EventoResponse:
    tipo = getattr(evento, "tipo_evento", None)
    return EventoResponse(
        id=evento.id,
        area=tipo.area if tipo else "",
        tipo_evento=tipo.nombre if tipo else "",
        tipo_evento_id=evento.tipo_evento_id,
        descripcion=evento.descripcion,
        fuente=evento.fuente,
        estado=evento.estado,
        fecha_ocurrencia=evento.fecha_ocurrencia,
        fecha_creacion=evento.fecha_creacion,
        fecha_actualizacion=evento.fecha_actualizacion,
        latitud=evento.latitud,
        longitud=evento.longitud,
        usuario_id=evento.usuario_id,
    )

