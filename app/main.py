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
