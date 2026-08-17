from pydantic import field_validator

from app.modules.events.schemas import EventoCommonCreate, RequestModel


PRIORIDADES_VALIDAS = {"alta", "media", "baja"}


def _validar_prioridad(value: str | None) -> str | None:
    if value is None:
        return value
    prioridad = value.strip().lower()
    if prioridad not in PRIORIDADES_VALIDAS:
        raise ValueError(f"prioridad invalida. Valores: {', '.join(sorted(PRIORIDADES_VALIDAS))}")
    return prioridad


class EventoVideoseguridadCreate(EventoCommonCreate):
    # User-friendly service reference. Example: "policia".
    servicio_actuante: str | None = None
    # Backwards compatible; prefer `servicio_actuante`.
    servicio_actuante_id: int | None = None
    # User-friendly camera reference (matches Camara.codigo). Example: "camara 1".
    camara: str | None = None
    # Backwards compatible; prefer `camara`.
    camara_id: int | None = None
    prioridad: str | None = None
    movil_comisionado: str | None = None
    supervisor_nombre: str | None = None
    observaciones: str | None = None

    @field_validator("prioridad")
    @classmethod
    def _check_prioridad(cls, value: str | None) -> str | None:
        return _validar_prioridad(value)


class EventoVideoseguridadUpdate(RequestModel):
    servicio_actuante: str | None = None
    servicio_actuante_id: int | None = None
    camara: str | None = None
    camara_id: int | None = None
    prioridad: str | None = None
    movil_comisionado: str | None = None
    supervisor_nombre: str | None = None
    observaciones: str | None = None

    @field_validator("prioridad")
    @classmethod
    def _check_prioridad(cls, value: str | None) -> str | None:
        return _validar_prioridad(value)
