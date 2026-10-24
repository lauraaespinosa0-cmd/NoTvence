
"""Almacén de datos en memoria compartido entre las páginas HTML y la API JSON."""

from datetime import date, datetime


# =========================
# PRESENTACIONES POR CATEGORÍA
# =========================

PRESENTATIONS = {
    "Alimentos": [
        "Unidad", "Kg", "Gramos (g)", "Libra (lb)", "Litro (L)",
        "Mililitro (ml)", "Paquete", "Bolsa", "Caja", "Lata",
        "Frasco", "Botella", "Tarro", "Tubo", "Bandeja", "Racimo",
        "Docena", "Media docena", "Porción", "Sobre", "Pote",
        "Rollo", "Rebanada", "Unidad individual"
    ],
    "Bebidas": [
        "Litro (L)", "Mililitro (ml)", "Galón", "Botella", "Lata",
        "Caja", "Paquete", "Bolsa", "Frasco", "Tarro", "Vaso",
        "Sobre", "Unidad", "Garrafón", "Botellón"
    ],
    "Aseo": [
        "Unidad", "Litro (L)", "Mililitro (ml)", "Kg", "Gramos (g)",
        "Bolsa", "Paquete", "Caja", "Botella", "Frasco", "Tarro",
        "Galón", "Rollo", "Unidad individual", "Sobre", "Pote",
        "Aerosol", "Pastilla", "Barra", "Kit", "Recarga",
        "Repósito/recarga"
    ],
    "Medicamentos": [
        "Unidad", "Tableta", "Cápsula", "Comprimido", "Pastilla",
        "Sobre", "Ampolla", "Vial", "Frasco", "Botella", "Tubo",
        "Crema", "Gel", "Pomada", "Jarabe", "Gotas", "Spray",
        "Inhalador", "Parche", "Supositorio", "Jeringa", "Caja",
        "Blíster", "Paquete"
    ],
    "Otros": [
        "Unidad", "Kg", "Gramos (g)", "Litro (L)", "Mililitro (ml)",
        "Paquete", "Bolsa", "Caja", "Botella", "Frasco", "Tarro",
        "Galón", "Rollo", "Sobre", "Tubo", "Kit", "Juego", "Par",
        "Docena", "Metro", "Centímetro", "Pieza", "Set", "Bandeja",
        "Bulto", "Recarga", "Envase", "Contenedor"
    ],
}


# =========================
# SUBCATEGORÍAS
# =========================

SUBCATEGORIES = {
    "Alimentos": [
        "Carnes", "Frutas", "Verduras", "Granos", "Cereales",
        "Panadería", "Lácteos", "Huevos", "Enlatados",
        "Salsas y condimentos", "Congelados", "Snacks"
    ],
    "Bebidas": [
        "Agua", "Jugos", "Gaseosas", "Bebidas lácteas", "Café",
        "Té y aromáticas", "Bebidas energéticas", "Bebidas deportivas"
    ],
    "Aseo": [
        "Limpieza del hogar", "Lavandería", "Cocina", "Baño",
        "Cuidado personal", "Papel y desechables", "Higiene oral",
        "Cuidado del cabello"
    ],
    "Medicamentos": [
        "Analgésicos", "Antigripales", "Digestivos", "Vitaminas",
        "Primeros auxilios", "Medicamentos para alergias",
        "Medicamentos para la piel", "Medicamentos para la tos"
    ],
    "Otros": [],
}


# =========================
# ICONOS Y ORDEN
# =========================

CATEGORY_ICONS = {
    "Alimentos": "🥣",
    "Bebidas": "🥤",
    "Aseo": "🧴",
    "Medicamentos": "💊",
    "Otros": "📦",
}

CATEGORY_ORDER = [
    "Alimentos",
    "Bebidas",
    "Aseo",
    "Medicamentos",
    "Otros",
]


# =========================
# DATOS EN MEMORIA
# =========================

PRODUCTS: list[dict] = []

# La lista de compras no modifica las cantidades del inventario.
SHOPPING_ITEMS: dict[str, dict] = {
    product["codigo"]: {"cantidad": 0, "comprado": False}
    for product in PRODUCTS
}

SHOPPING_REMOVED: set[str] = set()
CUSTOM_SHOPPING_ITEMS: dict[str, dict] = {}


# =========================
# FUNCIONES DE ALERTAS
# =========================

def product_alerts(quantity, expiration, stock_limit=3) -> list[str]:
    """
    Devuelve todas las alertas que correspondan al producto.

    Alertas posibles:
    - Stock bajo
    - Por vencer
    - Vencido

    Un producto puede tener varias alertas simultáneamente.
    stock_limit representa el límite mínimo de existencias.
    """
    alertas = []

    # Convertir cantidad a número.
    try:
        cantidad = float(quantity or 0)
    except (TypeError, ValueError):
        cantidad = 0

    # Convertir el límite de stock.
    try:
        limite = float(3 if stock_limit is None else stock_limit)
    except (TypeError, ValueError):
        limite = 3

    # 1. Alerta de stock bajo.
    if cantidad <= limite:
        alertas.append("Stock bajo")

    # 2. Alertas de vencimiento.
    if expiration:
        try:
            if isinstance(expiration, datetime):
                fecha_vencimiento = expiration.date()
            elif isinstance(expiration, date):
                fecha_vencimiento = expiration
            else:
                fecha_vencimiento = datetime.strptime(
                    str(expiration)[:10],
                    "%Y-%m-%d",
                ).date()

            dias_restantes = (
                fecha_vencimiento - date.today()
            ).days

            if dias_restantes < 0:
                alertas.append("Vencido")
            elif dias_restantes <= 7:
                alertas.append("Por vencer")

        except (ValueError, TypeError):
            # Una fecha inválida no debe detener el inventario.
            pass

    return alertas


def product_status(quantity, expiration, stock_limit=3):
    """
    Devuelve el estado principal y su clase visual.

    Se conserva para las pantallas antiguas que esperan un único
    estado. Para obtener todas las alertas, usar product_alerts().
    """
    alertas = product_alerts(
        quantity,
        expiration,
        stock_limit,
    )

    if "Stock bajo" in alertas:
        return "Stock bajo", "danger"

    if "Vencido" in alertas:
        return "Vencido", "danger"

    if "Por vencer" in alertas:
        return "Por vencer", "warning"

    return "Activo", "success"


# =========================
# LÍMITE DE STOCK DEL PRODUCTO
# =========================

def get_stock_limit(product: dict) -> float:
    """
    Obtiene el límite de stock del producto.

    En la base de datos la columna se llama stock_minimo.
    En algunas respuestas de la API se usa stock_minimo.
    """
    valor = product.get(
        "stock_minimo",
        product.get(
            "stock_bajo",
            product.get("limite_stock", 3),
        ),
    )

    try:
        return float(3 if valor is None else valor)
    except (TypeError, ValueError):
        return 3


def get_product_alerts(product: dict) -> list[str]:
    """Calcula las alertas de un producto usando su propio límite."""
    return product_alerts(
        product.get("cantidad"),
        product.get("vence"),
        get_stock_limit(product),
    )


# =========================
# DATOS DEL DASHBOARD
# =========================

def dashboard_data(products=None):
    """Prepara los datos que se mostrarán en el dashboard."""

    products = PRODUCTS if products is None else products

    total_units = sum(
        float(product.get("cantidad") or 0)
        for product in products
    )

    # Contar productos con una o varias alertas.
    active_alerts = 0
    expiring_products = []

    for product in products:
        # Recalcular las alertas con el límite personalizado.
        alertas = get_product_alerts(product)

        if alertas:
            active_alerts += 1

        # Un producto puede estar por vencer y tener stock bajo.
        if "Por vencer" in alertas:
            expiring_products.append(product)

    categories = sorted({
        product["categoria"]
        for product in products
        if product.get("categoria")
    })

    return {
        "products_count": len(products),
        "units_count": total_units,
        "alerts_count": active_alerts,
        "categories_count": len(categories),
        "recent_products": list(reversed(products[-3:])),
        "expiring_products": expiring_products[:3],
    }


# =========================
# BÚSQUEDA DE PRODUCTOS
# =========================

def find_product(codigo):
    """Busca un producto por su código."""

    return next(
        (
            product
            for product in PRODUCTS
            if product["codigo"] == codigo
        ),
        None,
    )


def next_product_code() -> str:
    """Genera el siguiente código disponible para un producto."""

    existentes = {
        product["codigo"]
        for product in PRODUCTS
        if product.get("codigo")
    }

    n = len(PRODUCTS) + 1
    codigo = f"NV-{n:03d}"

    while codigo in existentes:
        n += 1
        codigo = f"NV-{n:03d}"

    return codigo


# =========================
# CÓDIGOS DE LISTA DE COMPRAS
# =========================

def next_custom_shopping_code() -> str:
    """Genera el siguiente código para un artículo personalizado."""

    n = len(CUSTOM_SHOPPING_ITEMS) + 1
    codigo = f"COMPRA-{n:03d}"

    while codigo in CUSTOM_SHOPPING_ITEMS:
        n += 1
        codigo = f"COMPRA-{n:03d}"

    return codigo



def next_custom_shopping_code() -> str:
    """Genera el siguiente código disponible para un artículo de compra personalizado."""
    n = len(CUSTOM_SHOPPING_ITEMS) + 1
    codigo = f"COMPRA-{n:03d}"
    while codigo in CUSTOM_SHOPPING_ITEMS:
        n += 1
        codigo = f"COMPRA-{n:03d}"
    return codigo
