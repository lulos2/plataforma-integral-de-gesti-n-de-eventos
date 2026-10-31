from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.database import models as _models  # noqa: F401
from app.api.router import api_router
from app.modules.events.crud import (
    EventoAnuladoError,
    NumeracionNoConfiguradaError,
    NumeracionYaConfiguradaError,
    NumeroEventoDuplicadoError,
)
from app.modules.events.registry import sync_numeracion_areas, sync_servicios_actuantes, sync_tipos_evento
from app.modules.users.registry import (
    bootstrap_superadmin,
    ensure_single_admin_dios_user,
    migrate_legacy_superadmin_users,
    sync_permissions,
    sync_system_roles,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create schema and bootstrap allowed TipoEvento rows.
    Base.metadata.create_all(bind=engine)

    # Lightweight migration for existing databases.
    # SQLAlchemy create_all won't add columns to existing tables.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash TEXT"))
            conn.execute(
                text(
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                    "session_version INTEGER NOT NULL DEFAULT 0"
                )
            )
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre VARCHAR"))
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apellido VARCHAR"))
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS area VARCHAR"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usuarios_area ON usuarios (area)"))
            # El turno es del evento y de cada operacion, no una caracteristica fija del usuario (rotan).
            conn.execute(text("ALTER TABLE usuarios DROP COLUMN IF EXISTS turno"))
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_roles (
                        user_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                        PRIMARY KEY (user_id, role_id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_roles_user_id ON user_roles (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_roles_role_id ON user_roles (role_id)"))

            # Centro de Monitoreo (COM) - Fase 1: columnas nuevas en eventos y especializaciones.
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS turno VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS direccion VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS origen VARCHAR"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_eventos_origen ON eventos (origen)"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS recibio_nombre VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS recibio_funcion VARCHAR"))

            # Numeracion por area: cada evento guarda su area y el numero es unico dentro de ella
            # (el mismo numero puede existir en areas distintas). Antes era una secuencia global.
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS numero_evento INTEGER"))
            conn.execute(text("UPDATE eventos SET numero_evento = id WHERE numero_evento IS NULL"))
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN numero_evento DROP DEFAULT"))
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN numero_evento SET NOT NULL"))
            conn.execute(text("ALTER TABLE eventos DROP CONSTRAINT IF EXISTS uq_eventos_numero_evento"))
            conn.execute(text("DROP SEQUENCE IF EXISTS eventos_numero_evento_seq"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_eventos_numero_evento ON eventos (numero_evento)"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS area VARCHAR"))
            conn.execute(
                text(
                    "UPDATE eventos e SET area = t.area FROM tipos_evento t "
                    "WHERE e.tipo_evento_id = t.id AND e.area IS NULL"
                )
            )
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN area SET NOT NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_eventos_area ON eventos (area)"))
            conn.execute(
                text(
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'uq_eventos_area_numero'
                        ) THEN
                            ALTER TABLE eventos ADD CONSTRAINT uq_eventos_area_numero UNIQUE (area, numero_evento);
                        END IF;
                    END $$
                    """
                )
            )
            # Carga historica: modalidad y datos del registro original; ubicacion opcional.
            conn.execute(
                text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS modalidad VARCHAR NOT NULL DEFAULT 'nuevo'")
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_eventos_modalidad ON eventos (modalidad)"))
            for columna, tipo_sql in (
                ("registro_fecha", "TIMESTAMPTZ"),
                ("registro_responsable_nombre", "VARCHAR"),
                ("registro_responsable_apellido", "VARCHAR"),
                ("registro_turno", "VARCHAR"),
                ("registro_referencia", "VARCHAR"),
                ("digitalizado_por_nombre", "VARCHAR"),
                ("digitalizado_por_apellido", "VARCHAR"),
            ):
                conn.execute(text(f"ALTER TABLE eventos ADD COLUMN IF NOT EXISTS {columna} {tipo_sql}"))
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN latitud DROP NOT NULL"))
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN longitud DROP NOT NULL"))
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN ubicacion DROP NOT NULL"))
            # La auditoria tambien registra operaciones que no son sobre un evento (inicializar la numeracion).
            conn.execute(text("ALTER TABLE eventos_audit ALTER COLUMN evento_id DROP NOT NULL"))
            conn.execute(text("ALTER TABLE eventos_audit ADD COLUMN IF NOT EXISTS numeracion_area VARCHAR"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_eventos_audit_numeracion_area ON eventos_audit (numeracion_area)")
            )

            conn.execute(text("ALTER TABLE eventos_videoseguridad ADD COLUMN IF NOT EXISTS movil_comisionado VARCHAR"))
            conn.execute(text("ALTER TABLE eventos_videoseguridad ADD COLUMN IF NOT EXISTS supervisor_nombre VARCHAR"))
            conn.execute(text("ALTER TABLE eventos_videoseguridad ADD COLUMN IF NOT EXISTS observaciones TEXT"))
            # prioridad: viejas bases la tienen como entero (1/2/3); se migra a texto (alta/media/baja).
            # El ELSE preserva el valor si ya es texto, para que correr esto de nuevo no rompa nada.
            conn.execute(
                text(
                    """
                    ALTER TABLE eventos_videoseguridad ALTER COLUMN prioridad TYPE VARCHAR USING (
                        CASE prioridad::text
                            WHEN '1' THEN 'alta'
                            WHEN '2' THEN 'media'
                            WHEN '3' THEN 'baja'
                            ELSE prioridad::text
                        END
                    )
                    """
                )
            )

            conn.execute(text("ALTER TABLE eventos_zoonosis ADD COLUMN IF NOT EXISTS propietario VARCHAR"))
            conn.execute(text("ALTER TABLE eventos_intervenciones ADD COLUMN IF NOT EXISTS resultado TEXT"))

            # Cierre de eventos: cuando, quien y observaciones de cierre.
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS fecha_cierre TIMESTAMPTZ"))
            conn.execute(
                text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS cerrado_por_id INTEGER REFERENCES usuarios(id)")
            )
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS observaciones_cierre TEXT"))

            # Quien cerro (copia del nombre al momento del cierre) y anulacion de eventos.
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS cierre_origen VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS cierre_nombre VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS cierre_apellido VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS fecha_anulacion TIMESTAMPTZ"))
            conn.execute(
                text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS anulado_por_id INTEGER REFERENCES usuarios(id)")
            )
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS anulado_por_nombre VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS anulado_por_apellido VARCHAR"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS motivo_anulacion TEXT"))
            # Eventos ya cerrados antes de este cambio: se completa quien cerro desde su usuario.
            conn.execute(
                text(
                    """
                    UPDATE eventos e
                    SET cierre_origen = 'sistema', cierre_nombre = u.nombre, cierre_apellido = u.apellido
                    FROM usuarios u
                    WHERE e.cerrado_por_id = u.id AND e.cierre_origen IS NULL
                    """
                )
            )
            conn.execute(text("ALTER TABLE eventos_audit ADD COLUMN IF NOT EXISTS actor_area VARCHAR"))
            conn.execute(text("ALTER TABLE eventos_audit ADD COLUMN IF NOT EXISTS actor_turno VARCHAR"))

            # Estados: solo "abierto" y "cerrado". Lo que haya quedado en "en_proceso" pasa a "abierto".
            conn.execute(text("UPDATE eventos SET estado = 'abierto' WHERE estado = 'en_proceso'"))

    db = SessionLocal()
    try:
        sync_tipos_evento(db)
        sync_servicios_actuantes(db)
        sync_numeracion_areas(db)
        sync_permissions(db)
        sync_system_roles(db)
        migrate_legacy_superadmin_users(db)
        ensure_single_admin_dios_user(db)
        bootstrap_superadmin(db, get_settings())
        ensure_single_admin_dios_user(db)
        if engine.dialect.name == "postgresql":
            db.execute(text("ALTER TABLE usuarios DROP COLUMN IF EXISTS is_superuser"))
            db.execute(text("ALTER TABLE usuarios DROP COLUMN IF EXISTS rol_id CASCADE"))
            db.execute(text("ALTER TABLE poligonos DROP COLUMN IF EXISTS color_hex"))
            db.commit()
    finally:
        db.close()

    yield


app = FastAPI(title="API Municipalidad Rauch", version="1.0", lifespan=lifespan)

# Origenes permitidos para el frontend. En produccion definir CORS_ORIGINS (separados por coma).
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


@app.exception_handler(NumeracionNoConfiguradaError)
@app.exception_handler(NumeracionYaConfiguradaError)
@app.exception_handler(NumeroEventoDuplicadoError)
async def numeracion_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(EventoAnuladoError)
async def evento_anulado_handler(_: Request, exc: EventoAnuladoError):
    # Un evento anulado se conserva pero ya no admite cambios.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
def root():
    return {"name": app.title, "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello(name: str):
    # Backwards compatible demo endpoint.
    return {"message": f"Hello {name}"}
