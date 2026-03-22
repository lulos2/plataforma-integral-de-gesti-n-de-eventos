from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from app.database.base import Base


class ServicioActuante(Base):
    __tablename__ = "servicios_actuantes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False, unique=True, index=True)  # policia | transito | bomberos | same


class Camara(Base):
    __tablename__ = "camaras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("idx_camaras_geom", ubicacion, postgresql_using="gist"),
    )


class Luminaria(Base):
    __tablename__ = "luminarias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("idx_luminarias_geom", ubicacion, postgresql_using="gist"),
    )


class Patrullero(Base):
    __tablename__ = "patrulleros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("idx_patrulleros_geom", ubicacion, postgresql_using="gist"),
    )


class BotonAntipanico(Base):
    __tablename__ = "botones_antipanico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=False)

    __table_args__ = (
        Index("idx_botones_antipanico_geom", ubicacion, postgresql_using="gist"),
    )


class EventoVideoseguridad(Base):
    __tablename__ = "eventos_videoseguridad"

    evento_id = Column(
        Integer,
        ForeignKey("eventos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    servicio_actuante_id = Column(Integer, ForeignKey("servicios_actuantes.id"), nullable=False, index=True)

    # Opcional: una camara asociada (si el evento proviene de una o se vincula a una)
    camara_id = Column(Integer, ForeignKey("camaras.id"), nullable=True, index=True)

    prioridad = Column(Integer, nullable=True, index=True)  # 1 alta, 2 media, 3 baja, etc.

    evento = relationship("Evento")
    servicio_actuante = relationship("ServicioActuante")
    camara = relationship("Camara")


class EventoZoonosis(Base):
    __tablename__ = "eventos_zoonosis"

    evento_id = Column(
        Integer,
        ForeignKey("eventos.id", ondelete="CASCADE"),
        primary_key=True,
    )

    especie = Column(String, nullable=True)  # perro, gato, roedor, etc.
    observaciones = Column(Text, nullable=True)
    requiere_control_antirrabico = Column(Boolean, nullable=True)

    evento = relationship("Evento")


class Comercio(Base):
    __tablename__ = "comercios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razon_social = Column(String, nullable=False, index=True)
    rubro = Column(String, nullable=True, index=True)
    domicilio = Column(String, nullable=True)
    ubicacion = Column(Geometry("POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("idx_comercios_geom", ubicacion, postgresql_using="gist"),
    )


class EventoBromatologia(Base):
    __tablename__ = "eventos_bromatologia"

    evento_id = Column(
        Integer,
        ForeignKey("eventos.id", ondelete="CASCADE"),
        primary_key=True,
    )

    comercio_id = Column(Integer, ForeignKey("comercios.id"), nullable=True, index=True)
    acta_numero = Column(String, nullable=True, index=True)
    resultado = Column(String, nullable=True, index=True)  # ok | observacion | clausura | etc
    observaciones = Column(Text, nullable=True)

    evento = relationship("Evento")
    comercio = relationship("Comercio")


class EventoIntervencion(Base):
    __tablename__ = "eventos_intervenciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True)

    servicio_actuante_id = Column(Integer, ForeignKey("servicios_actuantes.id"), nullable=False, index=True)
    actor_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)  # quien registro

    asignado_en = Column(DateTime(timezone=True), nullable=True, index=True)
    arribo_en = Column(DateTime(timezone=True), nullable=True, index=True)
    cerrado_en = Column(DateTime(timezone=True), nullable=True, index=True)

    notas = Column(Text, nullable=True)
    extra = Column(JSONB, nullable=True)

    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    evento = relationship("Evento")
    servicio_actuante = relationship("ServicioActuante")
    actor_usuario = relationship("Usuario")

