from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, String, Float
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

    # Información
    descripcion = Column(Text)
    fuente = Column(String, nullable=False, server_default="manual", index=True)  # manual | automatico | integracion_x
    estado = Column(String, nullable=False, server_default="abierto", index=True)  # abierto | en_proceso | cerrado
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

    # Auditoría
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    tipo_evento = relationship("TipoEvento")
    usuario = relationship("Usuario")

    __table_args__ = (
        Index("idx_eventos_geom", ubicacion, postgresql_using="gist"),
    )


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
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True)

    accion = Column(String, nullable=False)  # create | update | delete
    actor_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    fecha = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    detalle = Column(JSONB, nullable=True)

    evento = relationship("Evento")
    actor_usuario = relationship("Usuario")
