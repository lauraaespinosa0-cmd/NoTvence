
"""Esquemas Pydantic para la API JSON de NOTVENCE."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Categoria = Literal[
    "Alimentos",
    "Bebidas",
    "Aseo",
    "Medicamentos",
    "Otros",
]

EstadoClase = Literal["success", "warning", "danger"]

TipoAlerta = Literal[
    "Stock bajo",
    "Por vencer",
    "Vencido",
]


class ProductBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    categoria: Categoria
    subcategoria: str | None = Field(default=None, max_length=100)
    presentacion: str = Field(min_length=1, max_length=60)
    cantidad: float = Field(ge=0)
    stock_minimo: float = Field(default=3, ge=0)
    ubicacion: str = Field(min_length=1, max_length=80)
    vence: str | None = Field(
        default=None,
        description="Fecha de vencimiento en formato YYYY-MM-DD",
    )

    @field_validator("nombre", "presentacion", "ubicacion")
    @classmethod
    def validar_texto_no_vacio(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Este campo no puede estar vacío")

        return value

    @field_validator("vence")
    @classmethod
    def validar_fecha(cls, value: str | None) -> str | None:
        if not value:
            return None

        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "vence debe tener el formato YYYY-MM-DD"
            ) from exc

        return value


class ProductCreate(ProductBase):
    codigo: str | None = Field(
        default=None,
        description="Si no se envía, se genera automáticamente",
    )


class ProductUpdate(ProductBase):
    stock_minimo: float | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    codigo: str
    nombre: str
    categoria: str
    subcategoria: str | None = None
    presentacion: str
    cantidad: float
    stock_minimo: float = 3
    ubicacion: str
    vence: str
    alertas: list[TipoAlerta] = Field(default_factory=list)
    estado: str
    estado_clase: EstadoClase


class ShoppingItemCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    cantidad: int = Field(default=1, ge=0)


class ShoppingItemUpdate(BaseModel):
    cantidad_compra: int | None = Field(default=None, ge=0)
    comprado: bool | None = None


class ShoppingItemOut(BaseModel):
    codigo: str
    nombre: str
    presentacion: str | None = None
    cantidad_inventario: float | None = None
    compra_cantidad: int
    comprado: bool
    personalizado: bool


class DashboardOut(BaseModel):
    products_count: int
    units_count: float
    alerts_count: int
    categories_count: int
    recent_products: list[ProductOut]
    expiring_products: list[ProductOut]

