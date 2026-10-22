from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.areas import AREAS_VALIDAS, normalizar_area
from app.core.deps import areas_accesibles, require_permissions, verificar_acceso_area
from app.database.session import get_db
from app.modules.numeracion import crud
from app.modules.numeracion.schemas import (
    ConfiguradoPor,
    InicializarNumeracionRequest,
    NumeracionResponse,
)


router = APIRouter(prefix="/numeracion", tags=["Numeracion"])


def _to_response(contador) -> NumeracionResponse:
    configurado = None
    if contador.inicializada:
        configurado = ConfiguradoPor(
            usuario_id=contador.configurado_por_id,
            nombre=contador.configurado_por_nombre,
            apellido=contador.configurado_por_apellido,
        )
    return NumeracionResponse(
        area=contador.area,
        inicializada=contador.inicializada,
        siguiente_numero=contador.ultimo_numero + 1 if contador.inicializada else None,
        ultimo_informado=contador.ultimo_informado,
        ultimo_numero=contador.ultimo_numero if contador.inicializada else None,
        configurado_por=configurado,
        fecha_configuracion=contador.fecha_configuracion,
    )


def _area_valida(area: str) -> str:
    area = normalizar_area(area)
    if area not in AREAS_VALIDAS:
        raise HTTPException(status_code=404, detail="Area no encontrada")
    return area


@router.get("/", response_model=list[NumeracionResponse])
def listar_numeraciones(
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
):
    # Cada usuario ve el estado de la numeracion de las areas a las que tiene acceso.
    return [_to_response(c) for c in crud.listar_numeraciones(db, areas=areas_accesibles(usuario))]


@router.get("/{area}", response_model=NumeracionResponse)
def obtener_numeracion(
    area: str,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("eventos:read")),
):
    area = _area_valida(area)
    verificar_acceso_area(usuario, area)
    contador = crud.obtener_numeracion(db, area=area)
    if not contador:
        raise HTTPException(status_code=404, detail="Area no encontrada")
    return _to_response(contador)


@router.post("/{area}/inicializar", response_model=NumeracionResponse)
def inicializar_numeracion(
    area: str,
    data: InicializarNumeracionRequest,
    db: Session = Depends(get_db),
    usuario=Depends(require_permissions("numeracion:configurar")),
):
    area = _area_valida(area)
    verificar_acceso_area(usuario, area)
    try:
        contador = crud.inicializar_numeracion(
            db, area=area, ultimo_numero=data.ultimo_numero, actor_usuario_id=usuario.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not contador:
        raise HTTPException(status_code=404, detail="Area no encontrada")
    return _to_response(contador)
