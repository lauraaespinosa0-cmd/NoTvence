"""Endpoints de categorías y presentaciones."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_bearer_user
from app.products_repo import catalog_options

router = APIRouter(tags=["Categorías"])


@router.get("/categorias", summary="Lista las categorías disponibles")
def listar_categorias(user: str = Depends(get_bearer_user)):
    return {"categorias": sorted(catalog_options().keys())}


@router.get(
    "/categorias/{categoria}/presentaciones",
    summary="Presentaciones disponibles para una categoría",
)
def listar_presentaciones(categoria: str, user: str = Depends(get_bearer_user)):
    options = catalog_options()
    if categoria not in options:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría '{categoria}' no encontrada.",
        )
    return {"categoria": categoria, "presentaciones": options[categoria]["presentaciones"]}


@router.get(
    "/categorias/{categoria}/subcategorias",
    summary="Subcategorías disponibles para una categoría",
)
def listar_subcategorias(categoria: str, user: str = Depends(get_bearer_user)):
    options = catalog_options()
    if categoria not in options:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Categoría '{categoria}' no encontrada.",
        )
    return {"categoria": categoria, "subcategorias": options[categoria]["subcategorias"]}
