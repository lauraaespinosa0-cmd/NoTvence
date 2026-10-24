"""Endpoints CRUD para productos del inventario."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import products_repo
from app.database import get_connection
from app.deps import get_current_user_casa
from app.schemas import ProductCreate, ProductOut, ProductUpdate
from app.notificaciones import enviar_aviso


router = APIRouter(prefix="/productos", tags=["Productos"])


def obtener_correo_casa(id_casa: int) -> str | None:
    """Obtiene el correo del usuario asociado a la casa."""
    conexion = get_connection()

    try:
        cursor = conexion.cursor()

        cursor.execute(
            """
            SELECT correo
            FROM usuario
            WHERE id_casa = %s
            LIMIT 1
            """,
            (id_casa,),
        )

        resultado = cursor.fetchone()
        cursor.close()

        if resultado and resultado[0]:
            return resultado[0]

        return None

    finally:
        conexion.close()

        


def enviar_alertas_producto(
    producto: dict,
    id_casa: int,
) -> None:
    """Envía correos por las alertas activas del producto."""
    alertas = producto.get("alertas", [])

    if not alertas:
        return

    destinatario = obtener_correo_casa(id_casa)

    if not destinatario:
        logging.warning(
            "No se encontró un correo para la casa %s.",
            id_casa,
        )
        return

    tipos_correo = {
        "Stock bajo": "STOCK_BAJO",
        "Por vencer": "POR_VENCER",
        "Vencido": "VENCIDO",
    }

    for alerta in alertas:
        tipo = tipos_correo.get(alerta)

        if not tipo:
            continue

        try:
            enviar_aviso(
                destinatario=destinatario,
                nombre_producto=producto["nombre"],
                cantidad=producto["cantidad"],
                presentacion=producto["presentacion"],
                fecha_vencimiento=producto.get("vence"),
                tipo=tipo,
            )
        except Exception:
            logging.exception(
                "No se pudo enviar la alerta '%s' del producto '%s'.",
                alerta,
                producto.get("nombre"),
            )

def enviar_alertas_producto(producto: dict, id_casa: int) -> None:
    alertas = producto.get("alertas", [])

    print(f"[CORREO] Producto: {producto.get('nombre')}")
    print(f"[CORREO] Alertas detectadas: {alertas}")

    if not alertas:
        print("[CORREO] El producto no tiene alertas.")
        return

    destinatario = obtener_correo_casa(id_casa)
    print(f"[CORREO] Destinatario encontrado: {bool(destinatario)}")

    if not destinatario:
        print("[CORREO] No se encontró el correo del usuario.")
        return

    tipos_correo = {
        "Stock bajo": "STOCK_BAJO",
        "Por vencer": "POR_VENCER",
        "Vencido": "VENCIDO",
    }

    for alerta in alertas:
        tipo = tipos_correo.get(alerta)

        if not tipo:
            print(f"[CORREO] Tipo de alerta no reconocido: {alerta}")
            continue

        try:
            print(f"[CORREO] Intentando enviar: {tipo}")

            enviar_aviso(
                destinatario=destinatario,
                nombre_producto=producto["nombre"],
                cantidad=producto["cantidad"],
                presentacion=producto["presentacion"],
                fecha_vencimiento=producto.get("vence"),
                tipo=tipo,
            )

            print(f"[CORREO] Función de envío terminada: {tipo}")

        except Exception as error:
            print(f"[CORREO] ERROR: {type(error).__name__}: {error}")
            
@router.get(
    "",
    response_model=list[ProductOut],
    summary="Lista productos del inventario",
)
def listar_productos(
    categoria: str | None = None,
    estado: str | None = None,
    q: str | None = Query(
        default=None,
        description="Busca por nombre o código",
    ),
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa

    productos = products_repo.list_products(id_casa)

    if categoria:
        productos = [
            p for p in productos
            if p["categoria"] == categoria
        ]

    if estado:
        productos = [
            p for p in productos
            if p["estado"] == estado
            or estado in p.get("alertas", [])
        ]

    if q:
        needle = q.strip().lower()
        productos = [
            p for p in productos
            if needle in p["nombre"].lower()
            or needle in p["codigo"].lower()
        ]

    return productos


@router.get(
    "/{codigo}",
    response_model=ProductOut,
    summary="Obtiene un producto por código",
)
def obtener_producto(
    codigo: str,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa

    producto = products_repo.get_product(codigo, id_casa)

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo}' no encontrado.",
        )

    return producto


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un producto",
)
def crear_producto(
    payload: ProductCreate,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa

    producto = products_repo.create_product(
        {
            "nombre": payload.nombre,
            "categoria": payload.categoria,
            "subcategoria": payload.subcategoria,
            "presentacion": payload.presentacion,
            "cantidad": payload.cantidad,
            "stock_minimo": payload.stock_minimo,
            "ubicacion": payload.ubicacion,
            "vence": payload.vence,
        },
        id_casa,
    )

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La categoría indicada no existe.",
        )

    # Intentar enviar las alertas después de guardar el producto.
    try:
        enviar_alertas_producto(producto, id_casa)
    except Exception:
        # Un fallo de correo no debe deshacer el registro del producto.
        logging.exception(
            "No se pudieron procesar las alertas del producto '%s'.",
            producto.get("nombre"),
        )

    return producto


@router.put(
    "/{codigo}",
    response_model=ProductOut,
    summary="Actualiza un producto existente",
)
def actualizar_producto(
    codigo: str,
    payload: ProductUpdate,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa

    producto = products_repo.update_product(
        codigo,
        {
            "nombre": payload.nombre,
            "categoria": payload.categoria,
            "subcategoria": payload.subcategoria,
            "presentacion": payload.presentacion,
            "cantidad": payload.cantidad,
            "stock_minimo": payload.stock_minimo,
            "ubicacion": payload.ubicacion,
            "vence": payload.vence,
        },
        id_casa,
    )

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Producto '{codigo}' no encontrado "
                "o la categoría indicada no existe."
            ),
        )

    return producto


@router.delete(
    "/{codigo}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un producto",
)
def eliminar_producto(
    codigo: str,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    _, id_casa = user_casa

    eliminado = products_repo.delete_product(codigo, id_casa)

    if not eliminado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{codigo}' no encontrado.",
        )

    return None