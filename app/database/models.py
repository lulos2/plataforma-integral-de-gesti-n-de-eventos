"""
Import side effects: registering SQLAlchemy models with Base.metadata.

Keep this separate from app.database.base to avoid surprising import cycles.
"""

from __future__ import annotations

# Users
from app.modules.users.models import Rol, Usuario  # noqa: F401

# Events core + domain models
from app.modules.events.models import Evento, EventoAudit, TipoEvento  # noqa: F401
from app.modules.events.models_domain import (  # noqa: F401
    BotonAntipanico,
    Camara,
    Comercio,
    EventoBromatologia,
    EventoIntervencion,
    EventoVideoseguridad,
    EventoZoonosis,
    Luminaria,
    Patrullero,
    ServicioActuante,
)

