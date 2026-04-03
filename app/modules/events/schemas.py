from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.core.serialization import ArgentinaResponseModel


class RequestModel(BaseModel):
    # Reject unknown fields in incoming requests (e.g. "id" on POST).
    model_config = ConfigDict(extra="forbid")


class ResponseModel(ArgentinaResponseModel):
    pass


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


class EventoCommonCreate(RequestModel):
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime | None = None
    latitud: float
    longitud: float


class EventoCreate(EventoBase):
    servicio_actuante_id: int | None = None  # requerido para videoseguridad


class IntervencionCreate(RequestModel):
    servicio_actuante_id: int
    actor_usuario_id: int
    asignado_en: datetime | None = None
    arribo_en: datetime | None = None
    cerrado_en: datetime | None = None
    notas: str | None = None
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
    extra: dict | None = None
    fecha_creacion: datetime


class EventoUpdate(RequestModel):
    descripcion: str | None = None
    fuente: str | None = None
    estado: str | None = None
    fecha_ocurrencia: datetime | None = None
    latitud: float | None = None
    longitud: float | None = None
    # actor (auditoría real) se toma del usuario autenticado


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
    usuario_id: int
