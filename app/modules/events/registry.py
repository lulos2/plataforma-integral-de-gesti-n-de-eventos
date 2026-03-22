from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.events.models import TipoEvento
from app.modules.events.models_domain import ServicioActuante


@dataclass(frozen=True)
class TipoEventoDef:
    area: str
    nombre: str


# IMPORTANT:
# These are the only allowed (area, nombre) pairs. They should correspond to
# domain models you actually implement (tables/logic). The API must not accept
# arbitrary new types that have no backing model/meaning.
ALLOWED_TIPOS_EVENTO: tuple[TipoEventoDef, ...] = (
    # Videoseguridad
    TipoEventoDef(area="videoseguridad", nombre="robo"),
    TipoEventoDef(area="videoseguridad", nombre="disturbio"),
    TipoEventoDef(area="videoseguridad", nombre="accidente"),
    TipoEventoDef(area="videoseguridad", nombre="incendio"),
    TipoEventoDef(area="videoseguridad", nombre="denuncia"),

    # Zoonosis
    TipoEventoDef(area="zoonosis", nombre="mordedura"),
    TipoEventoDef(area="zoonosis", nombre="canino_suelto"),
    TipoEventoDef(area="zoonosis", nombre="control_antirrabico"),
    TipoEventoDef(area="zoonosis", nombre="control_vectores"),

    # Bromatologia
    TipoEventoDef(area="bromatologia", nombre="inspeccion"),
    TipoEventoDef(area="bromatologia", nombre="acta"),
    TipoEventoDef(area="bromatologia", nombre="denuncia"),
)


def sync_tipos_evento(db: Session) -> None:
    """Ensure DB contains exactly the allowed TipoEvento rows (adds missing; doesn't delete)."""
    existentes = {
        (t.area, t.nombre)
        for t in db.query(TipoEvento.area, TipoEvento.nombre).all()
    }

    nuevos = [
        TipoEvento(area=defn.area, nombre=defn.nombre)
        for defn in ALLOWED_TIPOS_EVENTO
        if (defn.area, defn.nombre) not in existentes
    ]

    if nuevos:
        db.add_all(nuevos)
        db.commit()


def sync_servicios_actuantes(db: Session) -> None:
    """Seed servicios actuantes (for filtering and interventions)."""
    allowed = ("policia", "transito", "bomberos", "same","indefinido")
    existentes = {row[0] for row in db.query(ServicioActuante.nombre).all()}
    nuevos = [ServicioActuante(nombre=n) for n in allowed if n not in existentes]
    if nuevos:
        db.add_all(nuevos)
        db.commit()
