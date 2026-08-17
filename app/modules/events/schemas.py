from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

from app.core.serialization import ArgentinaResponseModel


class RequestModel(BaseModel):
    # Reject unknown fields in incoming requests (e.g. "id" on POST).
    model_config = ConfigDict(extra="forbid")


class ResponseModel(ArgentinaResponseModel):
    pass


ORIGENES_VALIDOS = {"ojos_en_alerta", "linea_103", "monitoreo_propio", "fuerzas_seguridad"}


def _validar_origen(value: str | None) -> str | None:
    if value is None:
        return value
    origen = value.strip().lower()
    if origen not in ORIGENES_VALIDOS:
        raise ValueError(f"origen invalido. Valores: {', '.join(sorted(ORIGENES_VALIDOS))}")
    return origen


class TipoEventoBase(RequestModel):
    area: str
    nombre: str


class TipoEventoResponse(TipoEventoBase, ResponseModel):
    id: int


class EventoBase(RequestModel):
    tipo_evento_id: int
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime | None = None
    latitud: float
    longitud: float
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)


class EventoCommonCreate(RequestModel):
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime | None = None
    latitud: float
    longitud: float
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)


class EventoCreate(EventoBase):
    servicio_actuante_id: int | None = None  # requerido para videoseguridad


class IntervencionCreate(RequestModel):
    servicio_actuante_id: int
    actor_usuario_id: int
    asignado_en: datetime | None = None
    arribo_en: datetime | None = None
    cerrado_en: datetime | None = None
    notas: str | None = None
    resultado: str | None = None
    extra: dict | None = None


class IntervencionResponse(ResponseModel):
    id: int
    evento_id: int
    servicio_actuante_id: int
    actor_usuario_id: int
    asignado_en: datetime | None = None
    arribo_en: datetime | None = None
    cerrado_en: datetime | None = None
    notas: str | None = None
    resultado: str | None = None
    extra: dict | None = None
    fecha_creacion: datetime


class EventoUpdate(RequestModel):
    descripcion: str | None = None
    fuente: str | None = None
    estado: str | None = None
    fecha_ocurrencia: datetime | None = None
    latitud: float | None = None
    longitud: float | None = None
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None
    # actor (auditoría real) se toma del usuario autenticado

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)


class EventoResponse(ResponseModel):
    id: int
    area: str
    tipo_evento: str
    tipo_evento_id: int

    descripcion: str | None = None
    fuente: str
    estado: str
    fecha_ocurrencia: datetime | None = None
    fecha_creacion: datetime
    fecha_actualizacion: datetime | None = None

    latitud: float
    longitud: float
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    numero_evento: int
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None
    usuario_id: int

    # Datos propios del Centro de Monitoreo (solo presentes si area == "videoseguridad")
    servicio_actuante: str | None = None
    servicio_actuante_id: int | None = None
    camara: str | None = None
    camara_id: int | None = None
    prioridad: str | None = None
    movil_comisionado: str | None = None
    supervisor_nombre: str | None = None
    observaciones: str | None = None
