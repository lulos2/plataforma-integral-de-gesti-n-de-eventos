from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.areas import AREAS_VALIDAS
from app.modules.events.models import NumeracionArea, TipoEvento
from app.modules.events.models_domain import ServicioActuante


@dataclass(frozen=True)
class TipoEventoDef:
    area: str
    nombre: str  # identificador interno, sin tildes ni espacios (va en las URLs)
    etiqueta: str  # como se muestra en pantalla


# IMPORTANT:
# These are the only allowed (area, nombre) pairs. They should correspond to
# domain models you actually implement (tables/logic). The API must not accept
# arbitrary new types that have no backing model/meaning.
ALLOWED_TIPOS_EVENTO: tuple[TipoEventoDef, ...] = (
    # Videoseguridad (Centro de Monitoreo): motivos de llamado
    TipoEventoDef(area="videoseguridad", nombre="persona_sospechosa", etiqueta="Persona sospechosa"),
    TipoEventoDef(area="videoseguridad", nombre="robo_hurto", etiqueta="Robo o hurto"),
    TipoEventoDef(area="videoseguridad", nombre="peleas_via_publica", etiqueta="Peleas en vía pública"),
    TipoEventoDef(area="videoseguridad", nombre="ruidos_molestos", etiqueta="Ruidos molestos"),
    TipoEventoDef(area="videoseguridad", nombre="transito", etiqueta="Tránsito"),
    TipoEventoDef(area="videoseguridad", nombre="incendio", etiqueta="Incendio"),
    TipoEventoDef(area="videoseguridad", nombre="animales_sueltos", etiqueta="Animales sueltos"),
    TipoEventoDef(area="videoseguridad", nombre="cables_caidos", etiqueta="Cables caídos"),

    # Zoonosis
    # Lo que registra el area (informado por la direccion de Zoonosis). El control antirrabico no es un
    # tipo: se indica en el campo requiere_control_antirrabico del evento.
    TipoEventoDef(area="zoonosis", nombre="mordedura", etiqueta="Mordedura de perro o gato"),
    TipoEventoDef(area="zoonosis", nombre="canino_suelto", etiqueta="Perros sueltos"),
    TipoEventoDef(area="zoonosis", nombre="mosquitos_aedes", etiqueta="Mosquitos Aedes"),
    TipoEventoDef(area="zoonosis", nombre="roedores", etiqueta="Roedores en lugares públicos"),
    TipoEventoDef(area="zoonosis", nombre="murcielagos", etiqueta="Murciélagos"),
    TipoEventoDef(area="zoonosis", nombre="animales_ponzonosos", etiqueta="Animales ponzoñosos"),

    # Bromatologia
    TipoEventoDef(area="bromatologia", nombre="inspeccion", etiqueta="Inspección"),
    TipoEventoDef(area="bromatologia", nombre="acta", etiqueta="Acta"),
    TipoEventoDef(area="bromatologia", nombre="denuncia", etiqueta="Denuncia"),
)


def sync_tipos_evento(db: Session) -> None:
    """Ensure DB contains the allowed TipoEvento rows: adds missing ones and refreshes their etiqueta."""
    existentes = {(t.area, t.nombre): t for t in db.query(TipoEvento).all()}

    for defn in ALLOWED_TIPOS_EVENTO:
        fila = existentes.get((defn.area, defn.nombre))
        if fila is None:
            db.add(TipoEvento(area=defn.area, nombre=defn.nombre, etiqueta=defn.etiqueta))
        elif fila.etiqueta != defn.etiqueta:
            fila.etiqueta = defn.etiqueta
    db.commit()


def sync_numeracion_areas(db: Session) -> None:
    """Una fila de contador por area (sin inicializar). Nunca pisa un contador ya configurado."""
    existentes = {row[0] for row in db.query(NumeracionArea.area).all()}
    nuevos = [NumeracionArea(area=a) for a in AREAS_VALIDAS if a not in existentes]
    if nuevos:
        db.add_all(nuevos)
        db.commit()


def sync_servicios_actuantes(db: Session) -> None:
    """Seed servicios actuantes (for filtering and interventions)."""
    allowed = ("policia", "transito", "bomberos", "same")
    existentes = {row[0] for row in db.query(ServicioActuante.nombre).all()}
    nuevos = [ServicioActuante(nombre=n) for n in allowed if n not in existentes]
    if nuevos:
        db.add_all(nuevos)
        db.commit()
