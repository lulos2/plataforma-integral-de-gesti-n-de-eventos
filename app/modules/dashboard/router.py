from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permissions, resolver_area_consulta
from app.database.session import get_db
from app.modules.dashboard import crud
from app.modules.dashboard.schemas import ResumenResponse


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/resumen", response_model=ResumenResponse)
def resumen(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("estadisticas:read")),
    area: str | None = None,
):
    # Un usuario limitado a su area solo puede pedir la suya (403 si pide otra).
    return crud.obtener_resumen(db, area=resolver_area_consulta(usuario, area))
