"""Endpoints de la lista de compra (independiente del inventario)."""
from fastapi import APIRouter, Depends, HTTPException, status

from app import products_repo
from app.deps import get_current_user_casa
from app.schemas import ShoppingItemCreate, ShoppingItemOut, ShoppingItemUpdate
from app.store import (
    CUSTOM_SHOPPING_ITEMS,
    SHOPPING_ITEMS,
    SHOPPING_REMOVED,
    next_custom_shopping_code,
)

router = APIRouter(prefix="/lista-compra", tags=["Lista de compra"])


@router.get("", response_model=list[ShoppingItemOut], summary="Lista de compra actual")
def listar_lista_compra(user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    _, id_casa = user_casa
    products = products_repo.list_products(id_casa)

    for product in products:
        if product["codigo"] not in SHOPPING_REMOVED:
            SHOPPING_ITEMS.setdefault(product["codigo"], {"cantidad": 0, "comprado": False})

    items = [
        {
            "codigo": product["codigo"],
            "nombre": product["nombre"],
            "presentacion": product["presentacion"],
            "cantidad_inventario": product["cantidad"],
            "compra_cantidad": SHOPPING_ITEMS[product["codigo"]]["cantidad"],
            "comprado": SHOPPING_ITEMS[product["codigo"]]["comprado"],
            "personalizado": False,
        }
        for product in products
        if product["codigo"] in SHOPPING_ITEMS and product["codigo"] not in SHOPPING_REMOVED
    ]
    items += [
        {
            "codigo": codigo,
            "nombre": item["nombre"],
            "presentacion": item.get("unidad"),
            "cantidad_inventario": None,
            "compra_cantidad": item["cantidad"],
            "comprado": item["comprado"],
            "personalizado": True,
        }
        for codigo, item in CUSTOM_SHOPPING_ITEMS.items()
    ]
    return items


@router.post(
    "",
    response_model=ShoppingItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agrega un artículo de compra exclusivo (sin crear producto de inventario)",
)
def agregar_articulo(payload: ShoppingItemCreate, user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    codigo = next_custom_shopping_code()
    CUSTOM_SHOPPING_ITEMS[codigo] = {
        "nombre": payload.nombre,
        "cantidad": payload.cantidad,
        "comprado": False,
        "categoria": "Otros",
        "subcategoria": "",
        "unidad": "Unidad",
    }
    return {
        "codigo": codigo,
        "nombre": payload.nombre,
        "presentacion": "Unidad",
        "cantidad_inventario": None,
        "compra_cantidad": payload.cantidad,
        "comprado": False,
        "personalizado": True,
    }


@router.put("/{codigo}", response_model=ShoppingItemOut, summary="Actualiza cantidad o estado de compra de un artículo")
def actualizar_articulo(
    codigo: str,
    payload: ShoppingItemUpdate,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa
    personalizado = codigo in CUSTOM_SHOPPING_ITEMS

    if personalizado:
        item = CUSTOM_SHOPPING_ITEMS[codigo]
    elif codigo in SHOPPING_ITEMS or products_repo.get_product(codigo, id_casa):
        item = SHOPPING_ITEMS.setdefault(codigo, {"cantidad": 0, "comprado": False})
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artículo '{codigo}' no encontrado en la lista de compra.",
        )

    if payload.cantidad_compra is not None:
        item["cantidad"] = payload.cantidad_compra
    if payload.comprado is not None:
        item["comprado"] = payload.comprado

    if personalizado:
        return {
            "codigo": codigo,
            "nombre": item["nombre"],
            "presentacion": item.get("unidad"),
            "cantidad_inventario": None,
            "compra_cantidad": item["cantidad"],
            "comprado": item["comprado"],
            "personalizado": True,
        }

    producto = products_repo.get_product(codigo, id_casa)
    return {
        "codigo": codigo,
        "nombre": producto["nombre"],
        "presentacion": producto["presentacion"],
        "cantidad_inventario": producto["cantidad"],
        "compra_cantidad": item["cantidad"],
        "comprado": item["comprado"],
        "personalizado": False,
    }


@router.delete("/{codigo}", status_code=status.HTTP_204_NO_CONTENT, summary="Quita un artículo de la lista de compra")
def eliminar_articulo(codigo: str, user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    if codigo in CUSTOM_SHOPPING_ITEMS:
        CUSTOM_SHOPPING_ITEMS.pop(codigo, None)
    elif codigo in SHOPPING_ITEMS:
        SHOPPING_ITEMS.pop(codigo, None)
        SHOPPING_REMOVED.add(codigo)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artículo '{codigo}' no encontrado en la lista de compra.",
        )
