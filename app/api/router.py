from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.bromatologia.router import router as bromatologia_router
from app.modules.events.router import router as eventos_router
from app.modules.poligonos.router import router as poligonos_router
from app.modules.users.router import router as usuarios_router
from app.modules.videoseguridad.router import router as videoseguridad_router
from app.modules.zoonosis.router import router as zoonosis_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(usuarios_router)
api_router.include_router(eventos_router)
api_router.include_router(poligonos_router)
api_router.include_router(videoseguridad_router)
api_router.include_router(zoonosis_router)
api_router.include_router(bromatologia_router)
