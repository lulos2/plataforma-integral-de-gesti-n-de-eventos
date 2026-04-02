from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

from app.database.base import Base


class Poligono(Base):
    __tablename__ = "poligonos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)

    # Raw points provided by users in [latitud, longitud] form.
    puntos = Column(JSONB, nullable=False)
    area_m2 = Column(Float, nullable=False)
    geometria = Column(Geometry("POLYGON", srid=4326), nullable=False)

    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    fecha_actualizacion = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("idx_poligonos_geom", geometria, postgresql_using="gist"),
    )
