"""Consulta de direcciones y coordenadas contra Nominatim (OpenStreetMap), limitada al partido de Rauch.

Reglas del servicio publico de Nominatim que se respetan aca:
- se identifica la aplicacion con un User-Agent propio;
- como maximo una consulta por segundo (se serializa con un candado);
- se guardan en memoria las respuestas recientes para no repetir consultas iguales.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
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
PROVINCIA = "Buenos Aires"
PAIS = "Argentina"
# Contexto unico de toda busqueda: se agrega siempre, aunque el usuario ya haya escrito "Rauch".
CONTEXTO_BUSQUEDA = f"{PARTIDO}, {PROVINCIA}, {PAIS}"

# Lo que el usuario puede escribir de mas ("Larrea 250, Rauch, Buenos Aires"): se saca y se pone el contexto fijo.
_CONTEXTO_RE = re.compile(
    r"\b(partido\s+de\s+rauch|rauch|(provincia\s+de\s+)?buenos\s+aires|pcia\.?|argentina)\b", flags=re.IGNORECASE
)
# Palabras que no distinguen una calle de otra al compararlas ("Avenida San Martin" = "San Martin").
_PALABRAS_VIA = {"calle", "avenida", "av", "avda", "pasaje", "pje", "boulevard", "bulevar", "bv", "diagonal"}
_ARTICULOS = {"de", "del", "la", "las", "los", "el", "y"}
_SUFIJOS_NUMERO = {"n", "nro", "numero", "al"}


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


def _tokens(texto: str, *, sin_palabras_via: bool = False) -> list[str]:
    """Palabras en minuscula y sin tildes ("Hipólito" -> "hipolito")."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    palabras = re.findall(r"[a-z0-9]+", sin_tildes.lower())
    if sin_palabras_via:
        palabras = [p for p in palabras if p not in _PALABRAS_VIA and p not in _ARTICULOS]
    return palabras


def _misma_calle(pedida: str, devuelta: str) -> bool:
    """La calle devuelta es la pedida: todas las palabras pedidas estan en el nombre devuelto.
    ("Yrigoyen" y "Avenida Hipolito Yrigoyen" coinciden; "Mitre" y "Moreno" no.)"""
    pedidas = set(_tokens(pedida, sin_palabras_via=True))
    return bool(pedidas) and pedidas <= set(_tokens(devuelta, sin_palabras_via=True))


def _altura_numerica(numero: str | None) -> int | None:
    """'250' -> 250, '250 A' -> 250, '250-252' -> 250."""
    m = re.match(r"\s*(\d+)", numero or "")
    return int(m.group(1)) if m else None


def _separar_calle_altura(texto: str) -> tuple[str, int | None]:
    """'Larrea 250' -> ('Larrea', 250). Sin numero al final devuelve (texto, None)."""
    palabras = texto.replace(",", " ").split()
    if len(palabras) >= 2 and palabras[-1].isdigit() and len(palabras[-1]) <= 5:
        altura = int(palabras[-1])
        calle = palabras[:-1]
        # "Larrea nro 250", "Larrea n° 250", "Larrea al 250"
        while len(calle) > 1 and calle[-1].lower().strip(".°º") in _SUFIJOS_NUMERO:
            calle.pop()
        if any(c.isalpha() for c in " ".join(calle)):
            return " ".join(calle), altura
    return texto, None


def _quitar_contexto(texto: str) -> str:
    """Saca 'Rauch', 'Buenos Aires', 'Argentina' y sobrantes; el contexto se agrega siempre igual al consultar."""
    limpio = _CONTEXTO_RE.sub(" ", texto)
    limpio = " ".join(limpio.replace(",", " ").split())
    # Si solo quedo el contexto (o casi nada), se respeta lo que escribio el usuario.
    return limpio if sum(c.isalnum() for c in limpio) >= 3 else texto


def _a_ubicacion(item: dict, *, pedida: tuple[str, int] | None = None, es_punto: bool = False) -> UbicacionResponse | None:
    """Arma la ubicacion. `pedida` = (calle, altura) que escribio el operador, para validarla;
    `es_punto` = viene de un punto marcado en el mapa (nunca es una direccion verificada).
    Devuelve None si no sirve o si la calle devuelta no es la pedida."""
    try:
        latitud = float(item["lat"])
        longitud = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    d = item.get("address") or {}
    calle = d.get("road") or d.get("pedestrian") or d.get("footway") or d.get("path")
    altura = d.get("house_number") or None
    barrio = d.get("neighbourhood") or d.get("suburb") or d.get("quarter") or None
    localidad = d.get("town") or d.get("city") or d.get("village") or d.get("hamlet") or None
    nombre_lugar = str(item.get("name") or "").strip()

    if pedida is not None:
        if not calle:
            return None
        if altura:
            coincide = _misma_calle(pedida[0], calle)
        else:
            # Sin altura solo se acepta la calle exacta ("Escuela" no es "Acceso a la escuela").
            coincide = set(_tokens(pedida[0], sin_palabras_via=True)) == set(_tokens(calle, sin_palabras_via=True))
        if not coincide:
            return None  # otra calle: no es lo que se pidio

    nombre = None
    if calle:
        partes = [f"{calle} {altura}" if altura else calle, localidad]
        # Un lugar con nombre propio (Municipalidad, Hospital...) se informa aparte de la direccion.
        if nombre_lugar and not _misma_calle(nombre_lugar, calle) and nombre_lugar != barrio:
            nombre = nombre_lugar
    else:
        # Sin calle (un barrio, un paraje, etc.): el nombre del lugar y la localidad.
        partes = [nombre_lugar or barrio, localidad]
    vistas: list[str] = []
    for p in partes:  # sin repetidos ("Belgrano, Belgrano") y sin partes vacias
        if p and p not in vistas:
            vistas.append(p)
    direccion = ", ".join(vistas) or str(item.get("display_name") or "").strip()
    if not direccion:
        return None

    verificada = (
        not es_punto
        and pedida is not None
        and altura is not None
        and _altura_numerica(altura) == pedida[1]
    )
    return UbicacionResponse(
        direccion=direccion,
        latitud=latitud,
        longitud=longitud,
        verificacion="verificada" if verificada else "aproximada",
        aproximada=not verificada,
        calle=calle,
        altura=altura,
        barrio=barrio,
        localidad=localidad,
        nombre=nombre,
    )


def _filtrar(datos, *, pedida: tuple[str, int] | None = None) -> list[UbicacionResponse]:
    """Resultados de Nominatim -> ubicaciones de Rauch, sin repetidos, las verificadas primero."""
    if not isinstance(datos, list):
        raise GeocodificacionNoDisponible("respuesta inesperada del servicio de mapas", sin_conexion=False)
    resultados: list[UbicacionResponse] = []
    vistos: set[tuple[str, float, float]] = set()
    for item in datos:
        if not isinstance(item, dict) or not _es_de_rauch(item.get("address") or {}):
            continue
        ubicacion = _a_ubicacion(item, pedida=pedida)
        if ubicacion is None:
            continue
        marca = (ubicacion.direccion, round(ubicacion.latitud, 5), round(ubicacion.longitud, 5))
        if marca in vistos:
            continue
        vistos.add(marca)
        resultados.append(ubicacion)
    resultados.sort(key=lambda u: u.verificacion != "verificada")  # estable: respeta el orden del proveedor
    return resultados[:MAX_RESULTADOS]


def buscar_direccion(texto: str) -> list[UbicacionResponse]:
    """Direccion escrita -> coincidencias dentro de Rauch (lista vacia si no hay).

    Siempre se busca en 'Rauch, Buenos Aires, Argentina', aunque el usuario ya haya escrito 'Rauch'.
    Si el texto es 'calle + altura' se hace una busqueda de domicilio (calle y altura por separado) y solo
    se aceptan resultados de esa calle; si no aparece nada, se busca como lugar o establecimiento conocido."""
    texto = _quitar_contexto(" ".join(texto.split()))
    calle, altura = _separar_calle_altura(texto)
    clave = ("buscar", " ".join(_tokens(texto)))
    guardado = _cache_leer(clave)
    if guardado is not None:
        return guardado

    resultados: list[UbicacionResponse] = []
    if altura is not None:
        datos = _consultar(
            "search",
            {"street": f"{altura} {calle}", "county": PARTIDO, "state": PROVINCIA, "country": PAIS,
             "addressdetails": 1, "limit": 10},
        )
        resultados = _filtrar(datos, pedida=(calle, altura))
    if not resultados:
        datos = _consultar(
            "search",
            {"q": f"{texto}, {CONTEXTO_BUSQUEDA}", "countrycodes": "ar", "addressdetails": 1, "limit": 10},
        )
        resultados = _filtrar(datos)

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
        # Es la direccion mas cercana al punto: nunca se la da por verificada.
        ubicacion = _a_ubicacion(datos, es_punto=True)
        if ubicacion is not None:
            # La coordenada que se devuelve es la que marco el operador, no la del centro de la calle.
            ubicacion = ubicacion.model_copy(update={"latitud": latitud, "longitud": longitud})

    # Se guarda tambien el "no encontrado" (False) para no repetir la consulta.
    _cache_guardar(clave, ubicacion if ubicacion is not None else False)
    return ubicacion
