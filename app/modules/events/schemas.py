from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime

from app.core.areas import validar_area
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


MODALIDADES_VALIDAS = {"nuevo", "historico"}


def _texto(value: str | None) -> str | None:
    return (value or "").strip() or None


class RegistroOriginal(RequestModel):
    """Datos del registro en papel que se esta digitalizando. Lo que no figura en el papel queda en null."""

    fecha: datetime | None = None
    responsable_nombre: str | None = None
    responsable_apellido: str | None = None
    area: str
    turno: str | None = None
    referencia: str | None = None  # libro, folio o pagina

    @field_validator("fecha")
    @classmethod
    def _check_fecha(cls, value: datetime | None) -> datetime | None:
        return _fecha_con_zona(value)

    @field_validator("area")
    @classmethod
    def _check_area(cls, value: str) -> str:
        area = validar_area(value)
        if area is None:
            raise ValueError("el area del registro original es obligatoria")
        return area

    @field_validator("turno")
    @classmethod
    def _check_turno(cls, value: str | None) -> str | None:
        return _validar_turno(_texto(value))

    @field_validator("responsable_nombre", "responsable_apellido", "referencia")
    @classmethod
    def _check_texto(cls, value: str | None) -> str | None:
        return _texto(value)


class CierreOriginal(RequestModel):
    """Cierre tal como figura en el papel. No se completa con datos de quien digitaliza."""

    nombre: str | None = None
    apellido: str | None = None
    fecha: datetime | None = None
    observaciones: str | None = None

    @field_validator("fecha")
    @classmethod
    def _check_fecha(cls, value: datetime | None) -> datetime | None:
        return _fecha_con_zona(value)

    @field_validator("nombre", "apellido", "observaciones")
    @classmethod
    def _check_texto(cls, value: str | None) -> str | None:
        return _texto(value)


class CargaMixin(RequestModel):
    # "nuevo": el sistema asigna el numero y el estado inicial es abierto.
    # "historico": se digitaliza un registro en papel; conserva su numero, fechas y responsables originales.
    modalidad: str = "nuevo"
    numero_evento: int | None = Field(default=None, ge=1)  # solo historico: el numero original
    registro_original: RegistroOriginal | None = None
    cierre_original: CierreOriginal | None = None  # solo historico cerrado

    @field_validator("modalidad")
    @classmethod
    def _check_modalidad(cls, value: str) -> str:
        modalidad = value.strip().lower()
        if modalidad not in MODALIDADES_VALIDAS:
            raise ValueError(f"modalidad invalida. Valores: {', '.join(sorted(MODALIDADES_VALIDAS))}")
        return modalidad

    @model_validator(mode="after")
    def _check_carga(self):
        # Ubicacion opcional, pero completa: o las dos coordenadas o ninguna.
        if (getattr(self, "latitud", None) is None) != (getattr(self, "longitud", None) is None):
            raise ValueError("latitud y longitud se envian juntas (o ninguna de las dos)")

        if self.modalidad == "nuevo":
            sobrantes = [
                n for n in ("numero_evento", "registro_original", "cierre_original") if getattr(self, n) is not None
            ]
            if sobrantes:
                raise ValueError(f"{', '.join(sobrantes)} solo se admite en la modalidad historico")
            if self.estado != "abierto":
                raise ValueError("un nuevo registro comienza en estado abierto")
            if _texto(self.observaciones_cierre):
                raise ValueError("observaciones_cierre solo se puede indicar al cerrar un evento")
            return self

        # historico
        if self.numero_evento is None:
            raise ValueError("numero_evento es obligatorio en una carga historica (es el numero del papel)")
        if self.registro_original is None:
            raise ValueError("registro_original es obligatorio en una carga historica")
        if _texto(self.observaciones_cierre):
            raise ValueError("en una carga historica las observaciones de cierre van en cierre_original")
        if self.estado == "cerrado" and self.cierre_original is None:
            raise ValueError("un historico cerrado necesita cierre_original")
        if self.estado == "abierto" and self.cierre_original is not None:
            raise ValueError("un historico abierto no lleva datos de cierre")
        return self


class EventoBase(CargaMixin):
    tipo_evento_id: int
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime  # obligatoria: cuando ocurrio el hecho (fecha_creacion es cuando se cargo)
    latitud: float | None = None
    longitud: float | None = None
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


class EventoCommonCreate(CargaMixin):
    descripcion: str | None = None
    fuente: str = "manual"
    estado: str = "abierto"
    fecha_ocurrencia: datetime  # obligatoria: cuando ocurrio el hecho (fecha_creacion es cuando se cargo)
    latitud: float | None = None
    longitud: float | None = None
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
    evento_id: int | None = None
    numeracion_area: str | None = None
    accion: str
    usuario_id: int
    usuario_nombre: str | None = None
    usuario_apellido: str | None = None
    area: str | None = None
    turno: str | None = None
    fecha: datetime | None = None
    detalle: dict | None = None


class RegistroOriginalResponse(ResponseModel):
    fecha: datetime | None = None
    responsable_nombre: str | None = None
    responsable_apellido: str | None = None
    area: str | None = None
    turno: str | None = None
    referencia: str | None = None


class DigitalizacionResponse(ResponseModel):
    # Quien incorporo el registro historico al sistema y cuando (distinto del responsable original).
    usuario_id: int | None = None
    nombre: str | None = None
    apellido: str | None = None
    fecha: datetime | None = None


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

    latitud: float | None = None
    longitud: float | None = None
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
    # "nuevo" o "historico". Solo los historicos traen registro_original y digitalizacion.
    modalidad: str = "nuevo"
    registro_original: RegistroOriginalResponse | None = None
    digitalizacion: DigitalizacionResponse | None = None
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
