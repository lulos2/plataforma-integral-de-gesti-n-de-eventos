from app.modules.events.schemas import EventoCommonCreate, RequestModel


class EventoZoonosisCreate(EventoCommonCreate):
    especie: str | None = None
    observaciones: str | None = None
    requiere_control_antirrabico: bool | None = None


class EventoZoonosisUpdate(RequestModel):
    especie: str | None = None
    observaciones: str | None = None
    requiere_control_antirrabico: bool | None = None
