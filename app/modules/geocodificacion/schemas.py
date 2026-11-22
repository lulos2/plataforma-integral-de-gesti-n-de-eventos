from typing import Literal

from pydantic import BaseModel


class UbicacionResponse(BaseModel):
    """Una ubicacion encontrada.

    `verificacion`:
    - "verificada": la calle y la altura que se pidieron coinciden con lo que devolvio el mapa
      (y queda dentro de Rauch);
    - "aproximada": se encontro la calle pero no esa altura, o es un lugar / barrio / punto del mapa.
    Si no se encontro nada, la busqueda devuelve una lista vacia: eso significa "no pudo verificarse",
    no que la direccion no exista.

    `direccion` es calle, altura y localidad. El barrio o zona viene aparte en `barrio`, y el nombre
    de un lugar conocido (municipalidad, hospital, etc.) en `nombre`, para no confundirlos con la direccion.
    `aproximada` se mantiene por compatibilidad: es True cuando `verificacion` no es "verificada".
    """

    direccion: str
    latitud: float
    longitud: float
    verificacion: Literal["verificada", "aproximada"]
    aproximada: bool
    calle: str | None = None
    altura: str | None = None
    barrio: str | None = None
    localidad: str | None = None
    nombre: str | None = None


class BusquedaInversaResponse(BaseModel):
    """Resultado de buscar la direccion de un punto. Si no hay nada, `encontrada` es False y el resto
    viene vacio: el operador puede completar la ubicacion a mano."""

    encontrada: bool
    ubicacion: UbicacionResponse | None = None
