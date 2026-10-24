"""CRUD de productos del inventario contra MySQL."""

from app.database import get_connection
from app.store import (
    PRESENTATIONS,
    SUBCATEGORIES,
    product_status,
    product_alerts,
)


def _codigo_to_id(codigo: str) -> int | None:
    """Convierte NV-001 en el ID del producto."""
    try:
        return int(codigo.split("-", 1)[1])
    except (IndexError, ValueError, AttributeError):
        return None


def _id_to_codigo(id_producto: int) -> str:
    """Convierte el ID en un código NV-XXX."""
    return f"NV-{id_producto:03d}"


def _row_to_product(row) -> dict:
    """Convierte una fila de MySQL en un diccionario de producto."""
    (
        id_producto,
        nombre,
        categoria,
        presentacion,
        subcategoria,
        cantidad,
        fecha_vencimiento,
        ubicacion,
        stock_minimo,
    ) = row

    cantidad = float(cantidad or 0)
    stock_minimo = float(3 if stock_minimo is None else stock_minimo)

    vence = (
        fecha_vencimiento.isoformat()
        if fecha_vencimiento
        else None
    )

    # Calcular cada alerta independientemente.
    alertas = product_alerts(
        cantidad,
        vence,
        stock_minimo,
    )

    # Conservar un estado principal para las pantallas existentes.
    estado, estado_clase = product_status(
        cantidad,
        vence,
        stock_minimo,
    )

    return {
        "codigo": _id_to_codigo(id_producto),
        "nombre": nombre,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "presentacion": presentacion or "Unidad",
        "cantidad": cantidad,
        "stock_minimo": stock_minimo,
        "ubicacion": ubicacion or "Sin ubicación",
        "vence": vence or "Sin fecha",
        "estado": estado,
        "estado_clase": estado_clase,
        "alertas": alertas,
    }


_SELECT_BASE = """
    SELECT
        p.id_producto,
        p.nombre_producto,
        c.nombre_categoria,
        COALESCE(pr.nombre_presentacion, p.presentacion),
        s.nombre_subcategoria,
        p.cantidad,
        p.fecha_vencimiento,
        GROUP_CONCAT(
            DISTINCT u.nombre_ubicacion SEPARATOR ', '
        ),
        p.stock_minimo
    FROM producto p
    INNER JOIN categoria c
        ON c.id_categoria = p.id_categoria
    LEFT JOIN subcategoria s
        ON s.id_subcategoria = p.id_subcategoria
    LEFT JOIN presentacion pr
        ON pr.id_presentacion = p.id_presentacion
    LEFT JOIN producto_ubicacion pu
        ON pu.id_producto = p.id_producto
    LEFT JOIN ubicacion u
        ON u.id_ubicacion = pu.id_ubicacion
    WHERE p.id_casa = %s
"""


def list_products(id_casa: int = 1) -> list[dict]:
    """Lista los productos de una casa."""
    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            _SELECT_BASE
            + """
            GROUP BY p.id_producto
            ORDER BY p.id_producto
            """,
            (id_casa,),
        )
        return [
            _row_to_product(row)
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conexion.close()


def get_product(
    codigo: str,
    id_casa: int = 1,
) -> dict | None:
    """Busca un producto por código y casa."""
    id_producto = _codigo_to_id(codigo)

    if id_producto is None:
        return None

    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            _SELECT_BASE
            + """
            AND p.id_producto = %s
            GROUP BY p.id_producto
            """,
            (id_casa, id_producto),
        )
        row = cursor.fetchone()
        return _row_to_product(row) if row else None
    finally:
        cursor.close()
        conexion.close()


def _resolve_categoria_id(
    cursor,
    categoria: str,
) -> int | None:
    cursor.execute(
        """
        SELECT id_categoria
        FROM categoria
        WHERE nombre_categoria = %s
        """,
        (categoria,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _resolve_subcategoria_id(
    cursor,
    subcategoria: str | None,
    id_categoria: int,
) -> int | None:
    if not subcategoria:
        return None

    cursor.execute(
        """
        SELECT id_subcategoria
        FROM subcategoria
        WHERE id_categoria = %s
          AND nombre_subcategoria = %s
        """,
        (id_categoria, subcategoria),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _resolve_presentacion_id(
    cursor,
    presentacion: str,
    id_categoria: int,
) -> int | None:
    cursor.execute(
        """
        SELECT id_presentacion
        FROM presentacion
        WHERE id_categoria = %s
          AND nombre_presentacion = %s
        """,
        (id_categoria, presentacion),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def catalog_options() -> dict:
    """Obtiene las opciones de categorías y catálogos."""
    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            """
            SELECT id_categoria, nombre_categoria
            FROM categoria
            """
        )

        categorias = {
            nombre: id_categoria
            for id_categoria, nombre in cursor.fetchall()
        }

        for categoria, id_categoria in categorias.items():
            for nombre in SUBCATEGORIES.get(categoria, []):
                cursor.execute(
                    """
                    INSERT IGNORE INTO subcategoria
                        (id_categoria, nombre_subcategoria)
                    VALUES (%s, %s)
                    """,
                    (id_categoria, nombre),
                )

            for nombre in PRESENTATIONS.get(categoria, []):
                cursor.execute(
                    """
                    INSERT IGNORE INTO presentacion
                        (id_categoria, nombre_presentacion)
                    VALUES (%s, %s)
                    """,
                    (id_categoria, nombre),
                )

        conexion.commit()

        cursor.execute(
            """
            SELECT
                c.nombre_categoria,
                s.nombre_subcategoria,
                NULL AS nombre_presentacion
            FROM categoria c
            LEFT JOIN subcategoria s
                ON s.id_categoria = c.id_categoria

            UNION ALL

            SELECT
                c.nombre_categoria,
                NULL,
                p.nombre_presentacion
            FROM categoria c
            LEFT JOIN presentacion p
                ON p.id_categoria = c.id_categoria
            """
        )

        opciones = {}

        for categoria, subcategoria, presentacion in cursor.fetchall():
            grupo = opciones.setdefault(
                categoria,
                {
                    "subcategorias": [],
                    "presentaciones": [],
                },
            )

            if (
                subcategoria
                and subcategoria not in grupo["subcategorias"]
            ):
                grupo["subcategorias"].append(subcategoria)

            if (
                presentacion
                and presentacion not in grupo["presentaciones"]
            ):
                grupo["presentaciones"].append(presentacion)

        return opciones
    finally:
        cursor.close()
        conexion.close()


def _find_or_create_ubicacion(
    cursor,
    nombre: str,
    id_casa: int,
) -> int:
    """Busca una ubicación o la crea si no existe."""
    cursor.execute(
        """
        SELECT id_ubicacion
        FROM ubicacion
        WHERE id_casa = %s
          AND nombre_ubicacion = %s
        """,
        (id_casa, nombre),
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO ubicacion (id_casa, nombre_ubicacion)
        VALUES (%s, %s)
        """,
        (id_casa, nombre),
    )
    return cursor.lastrowid


def _estado_producto_valido(estado: str) -> str:
    """Adapta el estado a los valores permitidos por la tabla."""
    return "Por vencer" if estado == "Vencido" else estado


def _set_ubicacion(
    cursor,
    id_producto: int,
    ubicacion: str,
    cantidad: int,
    id_casa: int,
) -> None:
    """Actualiza la ubicación asociada al producto."""
    cursor.execute(
        """
        DELETE FROM producto_ubicacion
        WHERE id_producto = %s
        """,
        (id_producto,),
    )

    ubicacion = (ubicacion or "").strip()

    if not ubicacion:
        return

    id_ubicacion = _find_or_create_ubicacion(
        cursor,
        ubicacion,
        id_casa,
    )

    cursor.execute(
        """
        INSERT INTO producto_ubicacion
            (id_producto, id_ubicacion, cantidad)
        VALUES (%s, %s, %s)
        """,
        (id_producto, id_ubicacion, cantidad),
    )


def create_product(
    data: dict,
    id_casa: int = 1,
) -> dict | None:
    """Crea un producto con su límite de stock."""
    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        id_categoria = _resolve_categoria_id(
            cursor,
            data["categoria"],
        )

        if id_categoria is None:
            return None

        presentacion = data.get("presentacion") or "Unidad"

        id_subcategoria = _resolve_subcategoria_id(
            cursor,
            data.get("subcategoria"),
            id_categoria,
        )

        id_presentacion = _resolve_presentacion_id(
            cursor,
            presentacion,
            id_categoria,
        )

        stock_minimo = data.get(
            "stock_bajo",
            data.get("stock_minimo", 3),
        )
        stock_minimo = 3 if stock_minimo is None else stock_minimo

        estado, _ = product_status(
            data["cantidad"],
            data.get("vence"),
            stock_minimo,
        )

        cursor.execute(
            """
            INSERT INTO producto (
                id_casa,
                id_categoria,
                id_subcategoria,
                id_presentacion,
                nombre_producto,
                descripcion,
                presentacion,
                cantidad,
                estado_producto,
                fecha_vencimiento,
                stock_minimo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                id_casa,
                id_categoria,
                id_subcategoria,
                id_presentacion,
                data["nombre"],
                data.get("descripcion", ""),
                presentacion,
                data["cantidad"],
                _estado_producto_valido(estado),
                data.get("vence") or None,
                stock_minimo,
            ),
        )

        id_producto = cursor.lastrowid

        _set_ubicacion(
            cursor,
            id_producto,
            data.get("ubicacion", ""),
            data["cantidad"],
            id_casa,
        )

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()

    return get_product(_id_to_codigo(id_producto), id_casa)


def update_product(
    codigo: str,
    data: dict,
    id_casa: int = 1,
) -> dict | None:
    """Actualiza un producto y su límite de stock."""
    id_producto = _codigo_to_id(codigo)

    if id_producto is None:
        return None

    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            """
            SELECT stock_minimo
            FROM producto
            WHERE id_producto = %s
              AND id_casa = %s
            """,
            (id_producto, id_casa),
        )
        existente = cursor.fetchone()

        if not existente:
            return None

        id_categoria = _resolve_categoria_id(
            cursor,
            data["categoria"],
        )

        if id_categoria is None:
            return None

        presentacion = data.get("presentacion") or "Unidad"

        id_subcategoria = _resolve_subcategoria_id(
            cursor,
            data.get("subcategoria"),
            id_categoria,
        )

        id_presentacion = _resolve_presentacion_id(
            cursor,
            presentacion,
            id_categoria,
        )

        # Si no llega un nuevo límite, conservar el existente.
        stock_minimo = data.get(
            "stock_bajo",
            data.get("stock_minimo", existente[0]),
        )

        if stock_minimo is None:
            stock_minimo = existente[0]

        estado, _ = product_status(
            data["cantidad"],
            data.get("vence"),
            stock_minimo,
        )

        cursor.execute(
            """
            UPDATE producto
            SET
                id_categoria = %s,
                id_subcategoria = %s,
                id_presentacion = %s,
                nombre_producto = %s,
                presentacion = %s,
                cantidad = %s,
                estado_producto = %s,
                fecha_vencimiento = %s,
                stock_minimo = %s
            WHERE id_producto = %s
              AND id_casa = %s
            """,
            (
                id_categoria,
                id_subcategoria,
                id_presentacion,
                data["nombre"],
                presentacion,
                data["cantidad"],
                _estado_producto_valido(estado),
                data.get("vence") or None,
                stock_minimo,
                id_producto,
                id_casa,
            ),
        )

        _set_ubicacion(
            cursor,
            id_producto,
            data.get("ubicacion", ""),
            data["cantidad"],
            id_casa,
        )

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()

    return get_product(codigo, id_casa)


def delete_product(
    codigo: str,
    id_casa: int = 1,
) -> bool:
    """Elimina un producto de la casa correspondiente."""
    id_producto = _codigo_to_id(codigo)

    if id_producto is None:
        return False

    conexion = get_connection()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM producto
            WHERE id_producto = %s
              AND id_casa = %s
            """,
            (id_producto, id_casa),
        )

        conexion.commit()
        return cursor.rowcount > 0

    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()
        conexion.close()


    if id_producto is None:
        return False

    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM producto WHERE id_producto = %s AND id_casa = %s", (id_producto, id_casa))
    conexion.commit()
    eliminado = cursor.rowcount > 0
    cursor.close()
    conexion.close()
    return eliminado
