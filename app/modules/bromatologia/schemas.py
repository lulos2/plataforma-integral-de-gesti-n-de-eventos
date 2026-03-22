from app.modules.events.schemas import EventoCommonCreate, RequestModel


class EventoBromatologiaCreate(EventoCommonCreate):
    comercio_id: int | None = None
    acta_numero: str | None = None
    resultado: str | None = None
    observaciones: str | None = None


class EventoBromatologiaUpdate(RequestModel):
    comercio_id: int | None = None
    acta_numero: str | None = None
    resultado: str | None = None
    observaciones: str | None = None

