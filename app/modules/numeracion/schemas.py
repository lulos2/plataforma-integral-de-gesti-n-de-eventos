from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.serialization import ArgentinaResponseModel


class InicializarNumeracionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Ultimo numero usado en el registro en papel. El proximo evento recibe este valor + 1.
    ultimo_numero: int = Field(ge=0)


class ConfiguradoPor(ArgentinaResponseModel):
    usuario_id: int | None = None
    nombre: str | None = None
    apellido: str | None = None


class NumeracionResponse(ArgentinaResponseModel):
    area: str
    inicializada: bool
    # Numero que recibira el proximo evento (null si todavia no se inicializo).
    siguiente_numero: int | None = None
    ultimo_informado: int | None = None
    # Ultimo numero asignado hasta ahora (null si todavia no se inicializo).
    ultimo_numero: int | None = None
    configurado_por: ConfiguradoPor | None = None
    fecha_configuracion: datetime | None = None
