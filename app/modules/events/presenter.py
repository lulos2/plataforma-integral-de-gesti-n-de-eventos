from app.modules.events.schemas import EventoResponse


def to_evento_response(evento) -> EventoResponse:
    tipo = getattr(evento, "tipo_evento", None)
    vs = getattr(evento, "videoseguridad", None)
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
        turno=evento.turno,
        direccion=evento.direccion,
        origen=evento.origen,
        numero_evento=evento.numero_evento,
        recibio_nombre=evento.recibio_nombre,
        recibio_funcion=evento.recibio_funcion,
        usuario_id=evento.usuario_id,
        servicio_actuante=vs.servicio_actuante.nombre if vs and vs.servicio_actuante else None,
        servicio_actuante_id=vs.servicio_actuante_id if vs else None,
        camara=vs.camara.codigo if vs and vs.camara else None,
        camara_id=vs.camara_id if vs else None,
        prioridad=vs.prioridad if vs else None,
        movil_comisionado=vs.movil_comisionado if vs else None,
        supervisor_nombre=vs.supervisor_nombre if vs else None,
        observaciones=vs.observaciones if vs else None,
    )

