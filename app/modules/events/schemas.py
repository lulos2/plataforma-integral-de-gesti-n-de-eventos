from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

from app.core.serialization import ARGENTINA_TZ, ArgentinaResponseModel
from app.core.turnos import validar_turno as _validar_turno


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


ESTADOS_VALIDOS = {"abierto", "cerrado"}


def _validar_estado(value: str | None) -> str | None:
    if value is None:
        return value
    estado = value.strip().lower()
    if estado not in ESTADOS_VALIDOS:
        raise ValueError(f"estado invalido. Valores: {', '.join(sorted(ESTADOS_VALIDOS))}")
    return estado


def _fecha_con_zona(value: datetime | None) -> datetime | None:
    # Una fecha sin zona horaria se interpreta como hora argentina (si no, la tomaria como UTC
    # y los eventos cercanos a medianoche caerian en el dia equivocado).
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=ARGENTINA_TZ)
    return value


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
    fecha_ocurrencia: datetime  # obligatoria: cuando ocurrio el hecho (fecha_creacion es cuando se cargo)
    latitud: float
    longitud: float
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None
    observaciones_cierre: str | None = None

    @field_validator("fecha_ocurrencia")
    @classmethod
    def _check_fecha_ocurrencia(cls, value: datetime) -> datetime:
        return _fecha_con_zona(value)

    @field_validator("turno")
    @classmethod
    def _check_turno(cls, value: str | None) -> str | None:
        return _validar_turno(value)

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)

    @field_validator("estado")
    @classmethod
    def _check_estado(cls, value: str | None) -> str | None:
        return _validar_estado(value)


class EventoCommonCreate(RequestModel):
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime  # obligatoria: cuando ocurrio el hecho (fecha_creacion es cuando se cargo)
    latitud: float
    longitud: float
    turno: str | None = None
    direccion: str | None = None
    origen: str | None = None
    recibio_nombre: str | None = None
    recibio_funcion: str | None = None
    observaciones_cierre: str | None = None

    @field_validator("fecha_ocurrencia")
    @classmethod
    def _check_fecha_ocurrencia(cls, value: datetime) -> datetime:
        return _fecha_con_zona(value)

    @field_validator("turno")
    @classmethod
    def _check_turno(cls, value: str | None) -> str | None:
        return _validar_turno(value)

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)

    @field_validator("estado")
    @classmethod
    def _check_estado(cls, value: str | None) -> str | None:
        return _validar_estado(value)


class EventoCreate(EventoBase):
    servicio_actuante_id: int | None = None  # requerido para videoseguridad


class IntervencionCreate(RequestModel):
    servicio_actuante_id: int
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
    observaciones_cierre: str | None = None
    # actor (auditoría real) se toma del usuario autenticado

    @field_validator("fecha_ocurrencia")
    @classmethod
    def _check_fecha_ocurrencia(cls, value: datetime | None) -> datetime | None:
        # Si no se quiere cambiar, se omite el campo. Mandar null explicito se rechaza.
        if value is None:
            raise ValueError("fecha_ocurrencia no puede ser null; omitirla para conservar la actual")
        return _fecha_con_zona(value)

    @field_validator("turno")
    @classmethod
    def _check_turno(cls, value: str | None) -> str | None:
        return _validar_turno(value)

    @field_validator("origen")
    @classmethod
    def _check_origen(cls, value: str | None) -> str | None:
        return _validar_origen(value)

    @field_validator("estado")
    @classmethod
    def _check_estado(cls, value: str | None) -> str | None:
        return _validar_estado(value)


class MotivoRequest(RequestModel):
    motivo: str

    @field_validator("motivo")
    @classmethod
    def _check_motivo(cls, value: str) -> str:
        motivo = value.strip()
        if not motivo:
            raise ValueError("el motivo no puede estar vacio")
        return motivo


class CierreResponse(ResponseModel):
    # "sistema": cerrado en la aplicacion. "historico": tomado del registro en papel.
    origen: str | None = None
    usuario_id: int | None = None
    nombre: str | None = None
    apellido: str | None = None
    fecha: datetime | None = None
    observaciones: str | None = None


class AnulacionResponse(ResponseModel):
    usuario_id: int | None = None
    nombre: str | None = None
    apellido: str | None = None
    fecha: datetime | None = None
    motivo: str | None = None


class AuditResponse(ResponseModel):
    id: int
    evento_id: int
    accion: str
    usuario_id: int
    usuario_nombre: str | None = None
    usuario_apellido: str | None = None
    area: str | None = None
    turno: str | None = None
    fecha: datetime | None = None
    detalle: dict | None = None


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

    # Cierre (solo presentes si el evento esta cerrado)
    fecha_cierre: datetime | None = None
    cerrado_por_id: int | None = None
    observaciones_cierre: str | None = None
    # Mismo dato de cierre en un solo objeto (null si el evento no esta cerrado).
    cierre: CierreResponse | None = None
    # Solo presente si el evento esta anulado.
    anulacion: AnulacionResponse | None = None

    # Datos propios del Centro de Monitoreo (solo presentes si area == "videoseguridad")
    servicio_actuante: str | None = None
    servicio_actuante_id: int | None = None
    camara: str | None = None
    camara_id: int | None = None
    prioridad: str | None = None
    movil_comisionado: str | None = None
    supervisor_nombre: str | None = None
    observaciones: str | None = None

    # Datos propios de Zoonosis (solo presentes si area == "zoonosis")
    especie: str | None = None
    propietario: str | None = None
    requiere_control_antirrabico: bool | None = None


class PuntoMapa(ResponseModel):
    id: int
    numero_evento: int
    latitud: float
    longitud: float
    area: str
    tipo_evento: str
    estado: str
    fecha: datetime | None = None


class EstadisticasPorTipo(ResponseModel):
    area: str
    tipo_evento: str
    cantidad: int


class EstadisticasResponse(ResponseModel):
    area: str | None = None
    total: int
    abiertos: int
    cerrados: int
    hoy: int
    semana: int
    mes: int
    por_tipo: list[EstadisticasPorTipo]
