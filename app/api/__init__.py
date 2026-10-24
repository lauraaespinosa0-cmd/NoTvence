"""API JSON de NOTVENCE, montada bajo el prefijo /api."""
from fastapi import APIRouter

from app.api import alertas, auth, categorias, dashboard, lista_compra, movimientos, productos

router = APIRouter(prefix="/api")
router.include_router(auth.router)
router.include_router(categorias.router)
router.include_router(productos.router)
router.include_router(alertas.router)
router.include_router(dashboard.router)
router.include_router(lista_compra.router)
router.include_router(movimientos.router)
