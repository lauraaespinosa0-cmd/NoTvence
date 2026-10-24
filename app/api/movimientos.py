"""Endpoints de movimientos de inventario (entradas, consumos y descartes)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app import movimientos_repo, products_repo
from app.deps import get_current_user_casa

router = APIRouter(prefix="/movimientos", tags=["Movimientos"])


class MovementCreate(BaseModel):
    codigo: str = Field(min_length=1, description="Código del producto (ej. NV-001)")
    tipo: Literal["Entrada", "Consumo", "Descarte"]
    cantidad: int = Field(gt=0)


class MovementOut(BaseModel):
    id_movimiento: int
    producto: str
    tipo: str
    cantidad: float
    fecha: str


@router.get("", response_model=list[MovementOut], summary="Lista los movimientos de la casa")
def listar_movimientos(user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    _, id_casa = user_casa
    rows = movimientos_repo.list_movements(id_casa)
    return [
        {
            "id_movimiento": row[0],
            "producto": row[1],
            "tipo": row[2],
            "cantidad": row[3],
            "fecha": row[4].isoformat() if row[4] else "",
        }
        for row in rows
    ]


@router.post("", response_model=MovementOut, status_code=status.HTTP_201_CREATED, summary="Registra un movimiento")
def crear_movimiento(payload: MovementCreate, user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    _, id_casa = user_casa

    producto = products_repo.get_product(payload.codigo, id_casa)
    if producto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")

    if payload.tipo in ("Consumo", "Descarte") and payload.cantidad > producto["cantidad"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay suficiente cantidad disponible.")

    id_producto = products_repo._codigo_to_id(payload.codigo)
    id_movimiento = movimientos_repo.create_movement(id_producto, payload.tipo, payload.cantidad)

    nueva_cantidad = (
        producto["cantidad"] + payload.cantidad
        if payload.tipo == "Entrada"
        else producto["cantidad"] - payload.cantidad
    )

    products_repo.update_product(
        payload.codigo,
        {
            "nombre": producto["nombre"],
            "categoria": producto["categoria"],
            "subcategoria": None if producto["subcategoria"] == "Sin subcategoría" else producto["subcategoria"],
            "presentacion": producto["presentacion"],
            "cantidad": nueva_cantidad,
            "ubicacion": producto["ubicacion"],
            "vence": None if producto["vence"] == "Sin fecha" else producto["vence"],
        },
        id_casa,
    )

    return {
        "id_movimiento": id_movimiento,
        "producto": producto["nombre"],
        "tipo": payload.tipo,
        "cantidad": payload.cantidad,
        "fecha": "",
    }
