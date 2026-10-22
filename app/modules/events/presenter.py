from app.modules.events.schemas import AnulacionResponse, AuditResponse, CierreResponse, EventoResponse


def to_evento_response(evento) -> EventoResponse:
    tipo = getattr(evento, "tipo_evento", None)
    vs = getattr(evento, "videoseguridad", None)
    zoo = getattr(evento, "zoonosis", None)
    cierre = None
    if evento.estado == "cerrado":
        cierre = CierreResponse(
            origen=evento.cierre_origen,
            usuario_id=evento.cerrado_por_id,
            nombre=evento.cierre_nombre,
            apellido=evento.cierre_apellido,
            fecha=evento.fecha_cierre,
            observaciones=evento.observaciones_cierre,
        )
    anulacion = None
    if evento.estado == "anulado":
        anulacion = AnulacionResponse(
            usuario_id=evento.anulado_por_id,
            nombre=evento.anulado_por_nombre,
            apellido=evento.anulado_por_apellido,
            fecha=evento.fecha_anulacion,
            motivo=evento.motivo_anulacion,
        )
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
        fecha_cierre=evento.fecha_cierre,
        cerrado_por_id=evento.cerrado_por_id,
        observaciones_cierre=evento.observaciones_cierre,
        cierre=cierre,
        anulacion=anulacion,
        servicio_actuante=vs.servicio_actuante.nombre if vs and vs.servicio_actuante else None,
        servicio_actuante_id=vs.servicio_actuante_id if vs else None,
        camara=vs.camara.codigo if vs and vs.camara else None,
        camara_id=vs.camara_id if vs else None,
        prioridad=vs.prioridad if vs else None,
        movil_comisionado=vs.movil_comisionado if vs else None,
        supervisor_nombre=vs.supervisor_nombre if vs else None,
        observaciones=(vs.observaciones if vs else None) or (zoo.observaciones if zoo else None),
        especie=zoo.especie if zoo else None,
        propietario=zoo.propietario if zoo else None,
        requiere_control_antirrabico=zoo.requiere_control_antirrabico if zoo else None,
    )



def to_audit_response(registro) -> AuditResponse:
    actor = registro.actor_usuario
    return AuditResponse(
        id=registro.id,
        evento_id=registro.evento_id,
        numeracion_area=registro.numeracion_area,
        accion=registro.accion,
        usuario_id=registro.actor_usuario_id,
        usuario_nombre=actor.nombre if actor else None,
        usuario_apellido=actor.apellido if actor else None,
        area=registro.actor_area,
        turno=registro.actor_turno,
        fecha=registro.fecha,
        detalle=registro.detalle,
    )
