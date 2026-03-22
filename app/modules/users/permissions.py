from __future__ import annotations

from enum import StrEnum


class PermissionCode(StrEnum):
    # Roles
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"

    # Users
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"


PERMISSION_DESCRIPTIONS: dict[PermissionCode, str] = {
    PermissionCode.ROLES_READ: "Listar roles y permisos",
    PermissionCode.ROLES_WRITE: "Crear/editar roles y asignar permisos",
    PermissionCode.USERS_READ: "Listar usuarios",
    PermissionCode.USERS_WRITE: "Crear/editar usuarios",
}

