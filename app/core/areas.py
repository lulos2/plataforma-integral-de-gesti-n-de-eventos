from __future__ import annotations

# Areas del municipio que cargan eventos. Coinciden con TipoEvento.area.
# "videoseguridad" es el Centro de Monitoreo (COM).
AREAS_VALIDAS: tuple[str, ...] = ("videoseguridad", "zoonosis", "bromatologia")


def normalizar_area(valor: str | None) -> str | None:
    limpio = (valor or "").strip().lower()
    return limpio or None


def validar_area(valor: str | None) -> str | None:
    area = normalizar_area(valor)
    if area is not None and area not in AREAS_VALIDAS:
        raise ValueError(f"area invalida. Valores permitidos: {', '.join(AREAS_VALIDAS)}")
    return area
