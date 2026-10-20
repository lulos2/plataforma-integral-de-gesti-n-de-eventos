from __future__ import annotations

# Turnos laborales validos.
TURNOS_VALIDOS: tuple[str, ...] = ("matutino", "vespertino", "nocturno")


def validar_turno(valor: str | None) -> str | None:
    if valor is None:
        return None
    turno = valor.strip().lower()
    if turno not in TURNOS_VALIDOS:
        raise ValueError(f"turno invalido. Valores: {', '.join(TURNOS_VALIDOS)}")
    return turno
