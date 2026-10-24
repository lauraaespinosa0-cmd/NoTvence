"""Endpoint de productos con alertas activas."""

from fastapi import APIRouter, Depends

from app import products_repo
from app.deps import get_current_user_casa
from app.schemas import ProductOut

router = APIRouter(tags=["Alertas"])


@router.get(
    "/alertas",
    response_model=list[ProductOut],
    summary="Lista productos con alertas activas",
)
def listar_alertas(
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    # Obtener el identificador de la casa del usuario autenticado.
    _, id_casa = user_casa

    # Consultar los productos de esa casa.
    productos = products_repo.list_products(id_casa)

    # Incluir productos que tengan una o varias alertas.
    productos_con_alertas = [
        producto
        for producto in productos
        if producto.get("alertas")
    ]

    return productos_con_alertas
