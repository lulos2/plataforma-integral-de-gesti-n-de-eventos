from sqlalchemy import Boolean, Column, Integer, DateTime, ForeignKey, Text, String, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from app.database.base import Base


class Evento(Base):

    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Clasificación
    tipo_evento_id = Column(Integer, ForeignKey("tipos_evento.id"), nullable=False, index=True)
    # Area del evento (la misma de su tipo). Se guarda aca para que area + numero_evento sea unico.
    area = Column(String, nullable=False, index=True)

    # Información
    descripcion = Column(Text)
    fuente = Column(String, nullable=False, server_default="manual", index=True)  # manual | automatico | integracion_x
    estado = Column(String, nullable=False, server_default="abierto", index=True)  # abierto | cerrado | anulado
    fecha_ocurrencia = Column(DateTime(timezone=True), nullable=True, index=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    fecha_actualizacion = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    # Geoposición
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=False)

    # Datos adicionales
    turno = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    origen = Column(String, nullable=True, index=True)  # ojos_en_alerta | linea_103 | monitoreo_propio | fuerzas_seguridad
    # Numero correlativo dentro del area: lo asigna el contador de numeracion_areas al crear el evento.
    numero_evento = Column(Integer, nullable=False, index=True)
    recibio_nombre = Column(String, nullable=True)
    recibio_funcion = Column(String, nullable=True)

    # Auditoría
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    # Cierre (se completan al pasar a "cerrado")
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    cerrado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    observaciones_cierre = Column(Text, nullable=True)
    # Quien cerro, copiado al momento del cierre: no cambia aunque despues se edite el perfil
    # o se desactive la cuenta. cierre_origen: "sistema" (cerrado en la app) | "historico" (papel).
    cierre_origen = Column(String, nullable=True)
    cierre_nombre = Column(String, nullable=True)
    cierre_apellido = Column(String, nullable=True)

    # Anulacion (estado "anulado"): el registro se conserva, nunca se borra.
    fecha_anulacion = Column(DateTime(timezone=True), nullable=True)
    anulado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    anulado_por_nombre = Column(String, nullable=True)
    anulado_por_apellido = Column(String, nullable=True)
    motivo_anulacion = Column(Text, nullable=True)

    tipo_evento = relationship("TipoEvento")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    videoseguridad = relationship("EventoVideoseguridad", uselist=False, viewonly=True)
    zoonosis = relationship("EventoZoonosis", uselist=False, viewonly=True)

    __table_args__ = (
        Index("idx_eventos_geom", ubicacion, postgresql_using="gist"),
        # El mismo numero puede existir en areas distintas, pero no repetirse dentro de una.
        UniqueConstraint("area", "numero_evento", name="uq_eventos_area_numero"),
    )


class NumeracionArea(Base):
    """Contador de numeracion de cada area, independiente de las demas y sin reinicio anual."""

    __tablename__ = "numeracion_areas"

    area = Column(String, primary_key=True)
    # Hasta que el administrador la inicialice (una sola vez), no se pueden crear eventos del area.
    inicializada = Column(Boolean, nullable=False, server_default="false")
    # Ultimo numero que figuraba en el registro en papel cuando se inicializo.
    ultimo_informado = Column(Integer, nullable=True)
    # Ultimo numero asignado. El proximo evento recibe ultimo_numero + 1.
    ultimo_numero = Column(Integer, nullable=False, server_default="0")
    configurado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    configurado_por_nombre = Column(String, nullable=True)
    configurado_por_apellido = Column(String, nullable=True)
    fecha_configuracion = Column(DateTime(timezone=True), nullable=True)


class TipoEvento(Base):
    __tablename__ = "tipos_evento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    area = Column(String, nullable=False, index=True)
    nombre = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("area", "nombre", name="uq_tipos_evento_area_nombre"),
    )


class EventoAudit(Base):
    __tablename__ = "eventos_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Null en las operaciones que no son sobre un evento (por ejemplo, inicializar la numeracion).
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=True, index=True)
    numeracion_area = Column(String, nullable=True, index=True)

    accion = Column(String, nullable=False)  # create | update | cerrar | reabrir | anular | inicializar_numeracion
    actor_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    # Area y turno laboral del usuario al momento de la operacion.
    actor_area = Column(String, nullable=True)
    actor_turno = Column(String, nullable=True)

    fecha = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    detalle = Column(JSONB, nullable=True)

    evento = relationship("Evento")
    actor_usuario = relationship("Usuario")
