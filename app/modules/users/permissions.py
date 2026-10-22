from __future__ import annotations

from enum import StrEnum


class PermissionCode(StrEnum):
    # Roles
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"

    # Users
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"

    # Eventos
    EVENTOS_READ = "eventos:read"
    EVENTOS_WRITE = "eventos:write"
    EVENTOS_ANULAR = "eventos:anular"
    EVENTOS_REABRIR = "eventos:reabrir"

    # Numeracion de eventos de cada area
    NUMERACION_CONFIGURAR = "numeracion:configurar"

    # Mapas, reportes y estadisticas
    ESTADISTICAS_READ = "estadisticas:read"

    # Ver todas las areas (si no lo tiene, el usuario solo accede a la suya)
    AREAS_ALL = "areas:all"


PERMISSION_DESCRIPTIONS: dict[PermissionCode, str] = {
    PermissionCode.ROLES_READ: "Listar roles y permisos",
    PermissionCode.ROLES_WRITE: "Crear/editar roles y asignar permisos",
    PermissionCode.USERS_READ: "Listar usuarios",
    PermissionCode.USERS_WRITE: "Crear/editar usuarios",
    PermissionCode.EVENTOS_READ: "Consultar eventos",
    PermissionCode.EVENTOS_WRITE: "Registrar y modificar eventos",
    PermissionCode.EVENTOS_ANULAR: "Anular eventos",
    PermissionCode.EVENTOS_REABRIR: "Reabrir eventos cerrados",
    PermissionCode.NUMERACION_CONFIGURAR: "Inicializar la numeracion de eventos del area",
    PermissionCode.ESTADISTICAS_READ: "Acceder a mapas, reportes y estadisticas",
    PermissionCode.AREAS_ALL: "Acceder a los datos de todas las areas",
}
