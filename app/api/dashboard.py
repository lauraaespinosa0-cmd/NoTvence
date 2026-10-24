"""Endpoint de resumen del inventario para el dashboard."""

from fastapi import APIRouter, Depends

from app import products_repo
from app.deps import get_current_user_casa
from app.schemas import DashboardOut
from app.store import dashboard_data

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", response_model=DashboardOut, summary="Resumen del inventario")
def obtener_dashboard(user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    _, id_casa = user_casa
    products = products_repo.list_products(id_casa)
    return dashboard_data(products)
