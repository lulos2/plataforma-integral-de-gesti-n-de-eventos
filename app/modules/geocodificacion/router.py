from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import require_permissions
from app.modules.geocodificacion import service
from app.modules.geocodificacion.schemas import BusquedaInversaResponse, UbicacionResponse

router = APIRouter(prefix="/geocodificacion", tags=["Geocodificacion"])


def _error_servicio(e: service.GeocodificacionNoDisponible) -> HTTPException:
    # 503: no se pudo conectar. 502: el servicio externo respondio algo que no sirve.
    # En ambos casos el frontend deja que el operador complete la ubicacion a mano.
    return HTTPException(
        status_code=503 if e.sin_conexion else 502,
        detail="El servicio de busqueda de ubicaciones no esta disponible. Podes completar la ubicacion manualmente.",
    )


@router.get("/buscar", response_model=list[UbicacionResponse])
def buscar(
    q: Annotated[str, Query(min_length=3, max_length=200, description="Direccion, ej. 'Castelli 61'")],
    usuario=Depends(require_permissions("eventos:write")),
):
    """Busca una direccion dentro de Rauch. Devuelve las coincidencias (lista vacia si no hay)."""
    texto = q.strip()
    if len(texto) < 3:
        raise HTTPException(status_code=422, detail="La direccion debe tener al menos 3 caracteres")
    try:
        return service.buscar_direccion(texto)
    except service.GeocodificacionNoDisponible as e:
        raise _error_servicio(e)


@router.get("/inversa", response_model=BusquedaInversaResponse)
def inversa(
    latitud: Annotated[float, Query(ge=-90, le=90)],
    longitud: Annotated[float, Query(ge=-180, le=180)],
    usuario=Depends(require_permissions("eventos:write")),
):
    """Direccion o referencia de un punto marcado en el mapa."""
    try:
        ubicacion = service.buscar_por_coordenadas(latitud, longitud)
    except service.GeocodificacionNoDisponible as e:
        raise _error_servicio(e)
    return BusquedaInversaResponse(encontrada=ubicacion is not None, ubicacion=ubicacion)
