from app.modules.events.schemas import EventoCommonCreate, RequestModel


class EventoVideoseguridadCreate(EventoCommonCreate):
    # User-friendly service reference. Example: "policia".
    servicio_actuante: str | None = None
    # Backwards compatible; prefer `servicio_actuante`.
    servicio_actuante_id: int | None = None
    # User-friendly camera reference (matches Camara.codigo). Example: "camara 1".
    camara: str | None = None
    # Backwards compatible; prefer `camara`.
    camara_id: int | None = None
    prioridad: int | None = None


class EventoVideoseguridadUpdate(RequestModel):
    servicio_actuante: str | None = None
    servicio_actuante_id: int | None = None
    camara: str | None = None
    camara_id: int | None = None
    prioridad: int | None = None
