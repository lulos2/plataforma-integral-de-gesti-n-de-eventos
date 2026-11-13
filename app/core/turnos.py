from __future__ import annotations

from datetime import datetime, time

from app.core.serialization import ARGENTINA_TZ

# Turnos laborales validos.
TURNOS_VALIDOS: tuple[str, ...] = ("matutino", "vespertino", "nocturno")


# Horarios de cada turno, por area ("*" = valen para todas las areas que no tengan los suyos).
# Formato: {"area": (("matutino", time(6), time(14)), ...)}
# Un turno puede cruzar la medianoche (desde > hasta).
# Una area sin horarios definidos (y sin "*") no tiene turno: queda en null, no se inventa.
HORARIOS_TURNOS: dict[str, tuple[tuple[str, time, time], ...]] = {
    # Centro de Monitoreo (COM): funciona las 24 horas todos los dias, en tres turnos de 8 horas
    # (confirmado por el municipio): 6 a 14, 14 a 22 y 22 a 6.
    # Zoonosis y Bromatologia no tienen turnos definidos: sin horarios cargados, su turno queda en null.
    "videoseguridad": (
        ("matutino", time(6), time(14)),
        ("vespertino", time(14), time(22)),
        ("nocturno", time(22), time(6)),
    ),
}


def turno_en(momento: datetime, area: str | None = None) -> str | None:
    """Turno laboral que corresponde a un momento (hora argentina). None si no hay horarios definidos."""
    horarios = HORARIOS_TURNOS.get(area or "") or HORARIOS_TURNOS.get("*")
    if not horarios:
        return None
    hora = momento.astimezone(ARGENTINA_TZ).time()
    for turno, desde, hasta in horarios:
        if desde <= hasta:
            if desde <= hora < hasta:
                return turno
        elif hora >= desde or hora < hasta:  # cruza la medianoche
            return turno
    return None


def validar_turno(valor: str | None) -> str | None:
    if valor is None:
        return None
    turno = valor.strip().lower()
    if turno not in TURNOS_VALIDOS:
        raise ValueError(f"turno invalido. Valores: {', '.join(TURNOS_VALIDOS)}")
    return turno
