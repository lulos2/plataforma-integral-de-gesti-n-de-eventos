from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


ARGENTINA_TZ = timezone(timedelta(hours=-3), name="GMT-3")


def to_argentina_iso(dt: datetime) -> str:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        localized = dt.replace(tzinfo=ARGENTINA_TZ)
    else:
        localized = dt.astimezone(ARGENTINA_TZ)
    return localized.isoformat(timespec="seconds")


class ArgentinaResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value):
        if isinstance(value, datetime):
            return to_argentina_iso(value)
        return value

