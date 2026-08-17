from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.database import models as _models  # noqa: F401
from app.api.router import api_router
from app.modules.events.registry import sync_servicios_actuantes, sync_tipos_evento
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
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre VARCHAR"))
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apellido VARCHAR"))
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

            # numero_evento: correlativo autogenerado. Se crea la secuencia, se agrega la columna
            # si falta, se completan filas viejas sin numero, y recien despues se fija el default
            # y las restricciones (para que funcione tanto en una base nueva como en una existente).
            conn.execute(text("CREATE SEQUENCE IF NOT EXISTS eventos_numero_evento_seq"))
            conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS numero_evento INTEGER"))
            conn.execute(
                text(
                    "UPDATE eventos SET numero_evento = nextval('eventos_numero_evento_seq') "
                    "WHERE numero_evento IS NULL"
                )
            )
            conn.execute(
                text(
                    "SELECT setval('eventos_numero_evento_seq', "
                    "COALESCE((SELECT MAX(numero_evento) FROM eventos), 0) + 1, false)"
                )
            )
            conn.execute(
                text("ALTER TABLE eventos ALTER COLUMN numero_evento SET DEFAULT nextval('eventos_numero_evento_seq')")
            )
            conn.execute(text("ALTER TABLE eventos ALTER COLUMN numero_evento SET NOT NULL"))
            conn.execute(
                text(
                    """
                    DO $$ BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'uq_eventos_numero_evento'
                        ) THEN
                            ALTER TABLE eventos ADD CONSTRAINT uq_eventos_numero_evento UNIQUE (numero_evento);
                        END IF;
                    END $$
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_eventos_numero_evento ON eventos (numero_evento)"))

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

    db = SessionLocal()
    try:
        sync_tipos_evento(db)
        sync_servicios_actuantes(db)
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
app.include_router(api_router)


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
