from pydantic import BaseModel


class UbicacionResponse(BaseModel):
    """Una ubicacion encontrada. `aproximada` es True cuando no se llego a una altura exacta
    (por ejemplo, se encontro la calle pero no el numero): el frontend puede avisarlo en pantalla."""

    direccion: str
    latitud: float
    longitud: float
    aproximada: bool


class BusquedaInversaResponse(BaseModel):
    """Resultado de buscar la direccion de un punto. Si no hay nada, `encontrada` es False y el resto
    viene vacio: el operador puede completar la ubicacion a mano."""

    encontrada: bool
    ubicacion: UbicacionResponse | None = None
