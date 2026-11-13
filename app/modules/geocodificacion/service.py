"""Consulta de direcciones y coordenadas contra Nominatim (OpenStreetMap), limitada al partido de Rauch.

Reglas del servicio publico de Nominatim que se respetan aca:
- se identifica la aplicacion con un User-Agent propio;
- como maximo una consulta por segundo (se serializa con un candado);
- se guardan en memoria las respuestas recientes para no repetir consultas iguales.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from app.modules.geocodificacion.schemas import UbicacionResponse

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "plataforma-eventos-municipio/1.0"
TIMEOUT_SEGUNDOS = 5
INTERVALO_MINIMO = 1.1  # segundos entre consultas a Nominatim
CACHE_VIGENCIA = 24 * 60 * 60  # segundos
CACHE_MAXIMO = 500
MAX_RESULTADOS = 5

PARTIDO = "Rauch"
CONTEXTO_BUSQUEDA = "Rauch, Buenos Aires, Argentina"


class GeocodificacionNoDisponible(Exception):
    """El servicio externo no respondio o respondio algo inesperado."""

    def __init__(self, mensaje: str, *, sin_conexion: bool):
        super().__init__(mensaje)
        # True: no se pudo conectar / tardo demasiado (503). False: respuesta invalida (502).
        self.sin_conexion = sin_conexion


_candado = threading.Lock()  # protege el cache
_candado_consulta = threading.Lock()  # serializa las consultas a Nominatim (maximo 1 por segundo)
_ultima_consulta = 0.0
_cache: OrderedDict[tuple, tuple[float, object]] = OrderedDict()


def _cache_leer(clave: tuple):
    with _candado:
        entrada = _cache.get(clave)
        if entrada is None:
            return None
        guardado_en, valor = entrada
        if time.monotonic() - guardado_en > CACHE_VIGENCIA:
            del _cache[clave]
            return None
        _cache.move_to_end(clave)
        return valor


def _cache_guardar(clave: tuple, valor) -> None:
    with _candado:
        _cache[clave] = (time.monotonic(), valor)
        _cache.move_to_end(clave)
        while len(_cache) > CACHE_MAXIMO:
            _cache.popitem(last=False)


def _consultar(ruta: str, params: dict):
    """Una consulta a Nominatim, respetando el ritmo maximo."""
    global _ultima_consulta
    url = f"{NOMINATIM_URL}/{ruta}?{urllib.parse.urlencode({**params, 'format': 'jsonv2', 'accept-language': 'es'})}"
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with _candado_consulta:
        espera = INTERVALO_MINIMO - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            time.sleep(espera)
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
                cuerpo = respuesta.read()
        except urllib.error.HTTPError as e:
            raise GeocodificacionNoDisponible(f"el servicio de mapas respondio {e.code}", sin_conexion=False)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GeocodificacionNoDisponible("no se pudo conectar con el servicio de mapas", sin_conexion=True)
        finally:
            _ultima_consulta = time.monotonic()

    try:
        return json.loads(cuerpo)
    except ValueError:
        raise GeocodificacionNoDisponible("respuesta invalida del servicio de mapas", sin_conexion=False)




def _es_de_rauch(direccion: dict) -> bool:
    texto = " ".join(str(direccion.get(k, "")) for k in ("state_district", "county", "municipality"))
    return PARTIDO.lower() in texto.lower()


def _armar_direccion(item: dict) -> str:
    d = item.get("address") or {}
    calle = d.get("road") or d.get("pedestrian") or d.get("footway") or d.get("path")
    barrio = d.get("neighbourhood") or d.get("suburb")
    localidad = d.get("town") or d.get("city") or d.get("village") or d.get("hamlet")
    if calle:
        calle = f"{calle} {d['house_number']}" if d.get("house_number") else calle
        partes = [calle, barrio, localidad]
    else:
        # Sin calle (un barrio, un lugar con nombre, etc.): nombre del lugar y localidad.
        nombre = str(item.get("name") or "").strip() or barrio
        partes = [nombre, localidad]
    # Sin repetidos ("Belgrano, Belgrano") y sin partes vacias.
    vistas: list[str] = []
    for p in partes:
        if p and p not in vistas:
            vistas.append(p)
    return ", ".join(vistas) or str(item.get("display_name") or "").strip()


def _a_ubicacion(item: dict) -> UbicacionResponse | None:
    try:
        latitud = float(item["lat"])
        longitud = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    direccion = _armar_direccion(item)
    if not direccion:
        return None
    # Aproximada = no se llego a una altura (numero de puerta) exacta.
    aproximada = not (item.get("address") or {}).get("house_number")
    return UbicacionResponse(direccion=direccion, latitud=latitud, longitud=longitud, aproximada=aproximada)


def buscar_direccion(texto: str) -> list[UbicacionResponse]:
    """Direccion escrita -> coincidencias dentro de Rauch (lista vacia si no hay)."""
    texto = " ".join(texto.split())
    clave = ("buscar", texto.lower())
    guardado = _cache_leer(clave)
    if guardado is not None:
        return guardado

    consulta = texto if PARTIDO.lower() in texto.lower() else f"{texto}, {CONTEXTO_BUSQUEDA}"
    datos = _consultar(
        "search",
        {"q": consulta, "countrycodes": "ar", "addressdetails": 1, "limit": 10},
    )
    if not isinstance(datos, list):
        raise GeocodificacionNoDisponible("respuesta inesperada del servicio de mapas", sin_conexion=False)

    resultados: list[UbicacionResponse] = []
    vistos: set[tuple[str, float, float]] = set()
    for item in datos:
        if not isinstance(item, dict) or not _es_de_rauch(item.get("address") or {}):
            continue
        ubicacion = _a_ubicacion(item)
        if ubicacion is None:
            continue
        marca = (ubicacion.direccion, round(ubicacion.latitud, 5), round(ubicacion.longitud, 5))
        if marca in vistos:
            continue
        vistos.add(marca)
        resultados.append(ubicacion)
        if len(resultados) >= MAX_RESULTADOS:
            break

    _cache_guardar(clave, resultados)
    return resultados


def buscar_por_coordenadas(latitud: float, longitud: float) -> UbicacionResponse | None:
    """Punto del mapa -> direccion o referencia (None si no hay nada o el punto cae fuera de Rauch)."""
    clave = ("inversa", round(latitud, 5), round(longitud, 5))
    guardado = _cache_leer(clave)
    if guardado is not None:
        return guardado or None

    datos = _consultar(
        "reverse",
        {"lat": latitud, "lon": longitud, "zoom": 18, "addressdetails": 1},
    )
    if not isinstance(datos, dict):
        raise GeocodificacionNoDisponible("respuesta inesperada del servicio de mapas", sin_conexion=False)

    ubicacion = None
    # Cuando no hay nada cerca, Nominatim devuelve {"error": "Unable to geocode"}.
    if "error" not in datos and _es_de_rauch(datos.get("address") or {}):
        ubicacion = _a_ubicacion(datos)
        if ubicacion is not None:
            # La coordenada que se devuelve es la que marco el operador, no la del centro de la calle.
            ubicacion = ubicacion.model_copy(update={"latitud": latitud, "longitud": longitud})

    # Se guarda tambien el "no encontrado" (False) para no repetir la consulta.
    _cache_guardar(clave, ubicacion if ubicacion is not None else False)
    return ubicacion
