from datetime import date, datetime

from app.core.serialization import ArgentinaResponseModel


class ResponseModel(ArgentinaResponseModel):
    pass


class Periodo(ResponseModel):
    desde: datetime
    hasta: datetime


class PeriodosResumen(ResponseModel):
    hoy: Periodo
    semana: Periodo
    mes: Periodo
    ultimos_30_dias: Periodo


class EvolucionDiaria(ResponseModel):
    fecha: date
    cantidad: int


class DistribucionTipo(ResponseModel):
    area: str
    tipo_evento: str
    cantidad: int


class UltimoEvento(ResponseModel):
    id: int
    numero_evento: int
    descripcion: str | None = None
    area: str
    tipo_evento: str
    fecha_ocurrencia: datetime | None = None
    direccion: str | None = None
    servicio_actuante: str | None = None
    estado: str


class ResumenResponse(ResponseModel):
    # None = todas las areas (solo para usuarios con acceso a todas).
    area: str | None = None
    generado_en: datetime
    periodos: PeriodosResumen

    eventos_mes: int
    eventos_semana: int
    eventos_hoy: int
    eventos_abiertos: int

    evolucion_diaria: list[EvolucionDiaria]
    distribucion_por_tipo: list[DistribucionTipo]
    ultimos_eventos: list[UltimoEvento]
