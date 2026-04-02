from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, field_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RolCreate(RequestModel):
    nombre: str
    permissions: list[str] = []


class PermissionResponse(ResponseModel):
    id: int
    code: str
    description: str | None = None


class RolResponse(ResponseModel):
    id: int
    nombre: str
    permissions: list[PermissionResponse] = []


class UsuarioCreate(RequestModel):
    username: str
    email: str
    nombre: str
    apellido: str
    rol_ids: list[int]
    password: str

    @field_validator("email")
    @classmethod
    def validar_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("email invalido")
        return email

    @field_validator("rol_ids")
    @classmethod
    def validar_rol_ids(cls, value: list[int]) -> list[int]:
        ids = list(dict.fromkeys(value))
        if not ids:
            raise ValueError("rol_ids debe tener al menos un rol")
        return ids


class UsuarioResponse(ResponseModel):
    id: int
    username: str
    email: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    roles: list[RolResponse] = []
    activo: bool
    fecha_creacion: datetime
