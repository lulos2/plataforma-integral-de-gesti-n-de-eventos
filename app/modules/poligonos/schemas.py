from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.serialization import ArgentinaResponseModel


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(ArgentinaResponseModel):
    pass


class Punto(RequestModel):
    latitud: float
    longitud: float

    @field_validator("latitud")
    @classmethod
    def validar_latitud(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("latitud fuera de rango [-90, 90]")
        return value

    @field_validator("longitud")
    @classmethod
    def validar_longitud(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("longitud fuera de rango [-180, 180]")
        return value


class PoligonoCreate(RequestModel):
    nombre: str
    descripcion: str | None = None
    puntos: list[Punto]

    @field_validator("puntos")
    @classmethod
    def validar_puntos(cls, value: list[Punto]) -> list[Punto]:
        if len(value) < 3:
            raise ValueError("se requieren al menos 3 puntos")
        return value

class PoligonoUpdate(RequestModel):
    nombre: str | None = None
    descripcion: str | None = None
    puntos: list[Punto] | None = None

    @field_validator("puntos")
    @classmethod
    def validar_puntos(cls, value: list[Punto] | None) -> list[Punto] | None:
        if value is None:
            return None
        if len(value) < 3:
            raise ValueError("se requieren al menos 3 puntos")
        return value

class PoligonoResponse(ResponseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    puntos: list[Punto]
    area_m2: float
    fecha_creacion: datetime
    fecha_actualizacion: datetime | None = None
