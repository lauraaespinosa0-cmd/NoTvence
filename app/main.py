import os
import re
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import products_repo
from app import movimientos_repo
from app.database import get_connection
from app.api import router as api_router
from app.deps import current_user
from app.store import (
    CATEGORY_ICONS,
    CATEGORY_ORDER,
    CUSTOM_SHOPPING_ITEMS,
    SHOPPING_ITEMS,
    SHOPPING_REMOVED,
    next_custom_shopping_code,
)

# =======================================
# INICIALIZACIÓN DE LA APLICACIÓN FASTAPI
# =======================================

app = FastAPI(title="NOTVENCE")
additional_cors_origins = [
    origin.strip()
    for origin in os.getenv("NOTVENCE_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=additional_cors_origins,
    allow_origin_regex=(
        r"^https?://(?:localhost|127(?:\.\d{1,3}){3}|"
        r"10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$"
    ),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "ngrok-skip-browser-warning",
    ],
)

# Configurar el directorio de templates (HTML)
templates = Jinja2Templates(directory="app/templates")

# Montar la carpeta /static para servir archivos estáticos (CSS, JS, imágenes)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Montar la API JSON bajo el prefijo /api
app.include_router(api_router)


@app.middleware("http")
async def no_cache_paginas(request: Request, call_next):
   
    response = await call_next(request)
    if not request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# =====================
# FUNCIONES AUXILIARES
# ======================

async def read_form(request: Request):
    body = (await request.body()).decode("utf-8")
    return {key: values[0] for key, values in parse_qs(body).items()}


PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


# Verifica si hay un usuario logueado; si no, redirige a login
def require_user(request: Request):
    username = current_user(request)
    if not username:
        # Retornar None y una redirección si no está autenticado
        return None, RedirectResponse(url="/?error=Debes iniciar sesión con una cuenta registrada.", status_code=303)
    return username, None

def current_user_casa(request: Request):
    """Obtiene el id de la casa asociada al usuario actual."""

    username = current_user(request)

    if not username:
        return None

    conexion = products_repo.get_connection()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT id_casa
        FROM usuario
        WHERE nombre = %s
        """,
        (username,)
    )

    usuario = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not usuario:
        return None

    return usuario[0]


def current_products(id_casa: int):
    """Productos del inventario de una casa, respaldados por MySQL (ver app/products_repo.py)."""
    return products_repo.list_products(id_casa)

def dashboard_data(products):
    """Prepara los datos que necesita el dashboard."""

    # Total de productos registrados
    products_count = len(products)

    # Total de unidades disponibles
    units_count = sum(
        product["cantidad"]
        for product in products
    )

    # Categorías utilizadas en los productos
    categories_count = len({
        product["categoria"]
        for product in products
        if product.get("categoria")
    })

    # Productos con alertas
    alerts = [
        product
        for product in products
        if product["estado"] in ["Por vencer", "Stock bajo", "Vencido"]
    ]

    alerts_count = len(alerts)

    # Últimos 3 productos registrados
    recent_products = products[-3:][::-1]

    # Productos próximos a vencer
    expiring_products = [
        product
        for product in products
        if product["estado"] == "Por vencer"
    ][:3]

    return {
        "products_count": products_count,
        "categories_count": categories_count,
        "units_count": units_count,
        "alerts_count": alerts_count,
        "recent_products": recent_products,
        "expiring_products": expiring_products,
    }



# ======================
# RUTAS DE AUTENTICACIÓN
# =======================

@app.get("/")
def login(request: Request, error: str | None = None, success: str | None = None):
    """Página de login/registro. Muestra registro si no hay usuarios, login si los hay."""
    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute("SELECT 1 FROM usuario LIMIT 1")
    hay_usuarios = cursor.fetchone() is not None
    cursor.close()
    conexion.close()

    mode = "login" if hay_usuarios else "register"
    return templates.TemplateResponse(
        request,
        "login_page.html",
        {"request": request, "error": error, "success": success, "mode": mode}
    )


@app.post("/registro")
async def register_post(request: Request):
    """Registra un usuario y crea automáticamente su casa."""

    form = await read_form(request)

    username = form.get("username", "").strip()
    email = form.get("email", "").strip()
    password = form.get("password", "").strip()

    # Validar campos
    if not username or not email or not password:
        return RedirectResponse(
            url="/?error=Completa usuario, correo y contraseña.",
            status_code=303
        )

    # Validar requisitos de la contraseña
    if not PASSWORD_PATTERN.match(password):
        return RedirectResponse(
            url="/?error=La contraseña debe tener mínimo 8 caracteres, incluyendo al menos una letra y un número.",
            status_code=303
        )

    conexion = products_repo.get_connection()
    cursor = conexion.cursor()

    # Verificar si el correo ya existe
    cursor.execute(
        "SELECT id_usuario FROM usuario WHERE correo = %s",
        (email,)
    )

    if cursor.fetchone():
        cursor.close()
        conexion.close()

        return RedirectResponse(
            url="/?error=Ese correo ya está registrado.",
            status_code=303
        )

    # Crear automáticamente la casa
    nombre_casa = f"Casa de {username}"

    cursor.execute(
        """
        INSERT INTO casa (nombre_hogar)
        VALUES (%s)
        """,
        (nombre_casa,)
    )

    id_casa = cursor.lastrowid

    # Crear el usuario relacionado con la casa
    cursor.execute(
        """
        INSERT INTO usuario (id_casa, nombre, correo, contrasena)
        VALUES (%s, %s, %s, %s)
        """,
        (id_casa, username, email, password)
    )

    conexion.commit()

    cursor.close()
    conexion.close()

    return RedirectResponse(
        url="/?success=Cuenta creada. Ahora inicia sesión.",
        status_code=303
    )


@app.post("/login")
async def login_post(request: Request):
    """Valida las credenciales usando MySQL."""

    form = await read_form(request)

    username = form.get("username", "").strip()
    password = form.get("password", "").strip()

    if not username or not password:
        return RedirectResponse(
            url="/?error=Completa usuario y contraseña.",
            status_code=303
        )

    conexion = products_repo.get_connection()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT id_usuario, nombre, contrasena
        FROM usuario
        WHERE nombre = %s
        """,
        (username,)
    )

    usuario = cursor.fetchone()

    cursor.close()
    conexion.close()

    # Verificar usuario y contraseña
    if not usuario or usuario[2] != password:
        return RedirectResponse(
            url="/?error=Usuario o contraseña incorrectos.",
            status_code=303
        )

    # Crear sesión
    response = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    response.set_cookie(
        "notvence_user",
        username,
        httponly=True,
        samesite="lax"
    )

    return response

@app.get("/logout")
def logout():
    """Cierra la sesión eliminando la cookie."""
    response = RedirectResponse(url="/?success=Sesión cerrada.", status_code=303)
    response.delete_cookie("notvence_user")
    return response


# ============================================================================
# RUTAS PRINCIPALES DE LA APLICACIÓN
# ============================================================================

@app.get("/dashboard")
def dashboard(request: Request):

    """Muestra el dashboard con resumen del inventario."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    products = products_repo.list_products(id_casa)
    movements_count = len(movimientos_repo.list_movements(id_casa)) if id_casa is not None else 0

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "current_page": "dashboard",
            "user": username,
            "movements_count": movements_count,
            **dashboard_data(products)
        }
    )


@app.get("/inventario")
def inventario(request: Request):
    """Muestra la tabla completa de productos del inventario."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    if id_casa is None:
        return RedirectResponse(url="/?error=No se encontró la casa del usuario.", status_code=303)

    products = current_products(id_casa)
    return templates.TemplateResponse(
        request,
        "inventario_page.html",
        {"request": request, "current_page": "inventario", "user": username, "products": products}
    )

@app.get("/producto/nuevo")
def nuevo_producto(request: Request):
    """Muestra el formulario para crear un nuevo producto."""
    username, redirect = require_user(request)

    if redirect:
        return redirect

    category_options = products_repo.catalog_options()
    return templates.TemplateResponse(
        request,
        "producto_nuevo_page.html",
        {
            "request": request,
            "current_page": "producto",
            "user": username,
            "subcategories": category_options.get("Alimentos", {}).get("subcategorias", []),
            "presentations": category_options.get("Alimentos", {}).get("presentaciones", []),
            "category_options": category_options,
        }
    )

@app.post("/producto/nuevo")
async def crear_producto(request: Request):
    """Procesa el formulario de nuevo producto y lo guarda en MySQL."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)

    if id_casa is None:
        return RedirectResponse(
            url="/inventario?error=No se encontró la casa del usuario.",
            status_code=303
        )

    form = await read_form(request)

    quantity = form.get("cantidad", "0").strip() or "0"
    expiration = form.get("vence", "").strip()
    categoria = form.get("categoria", "Otros").strip()

    producto = products_repo.create_product({
        "nombre": form.get("nombre", "").strip() or "Producto sin nombre",
        "categoria": categoria,
        "subcategoria": form.get("subcategoria", "").strip() or None,
        "descripcion": form.get("descripcion", "").strip(),
        "presentacion": form.get("presentacion", "").strip() or "Unidad",
        "cantidad": int(float(quantity)),
        "ubicacion": form.get("ubicacion", "").strip(),
        "vence": expiration or None,
    }, id_casa)

    if producto is None:
        return RedirectResponse(
            url="/producto/nuevo?error=Categoría no encontrada.",
            status_code=303
        )

    return RedirectResponse(
        url="/inventario?success=Producto registrado correctamente.",
        status_code=303
    )

@app.get("/producto/{codigo}")
def detalle_producto(request: Request, codigo: str):
    """READ: ruta dinamica que muestra un producto segun su codigo."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    product = products_repo.get_product(codigo, id_casa) if id_casa is not None else None
    if not product:
        return RedirectResponse(url="/inventario?error=Producto no encontrado.", status_code=303)

    return templates.TemplateResponse(
        request,
        "producto_detalle_page.html",
        {
            "request": request,
            "current_page": "inventario",
            "user": username,
            "product": product,
        }
    )


@app.get("/producto/{codigo}/editar")
def editar_producto(request: Request, codigo: str):
    """UPDATE: muestra el formulario para editar un producto existente."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    product = products_repo.get_product(codigo, id_casa) if id_casa is not None else None
    if not product:
        return RedirectResponse(url="/inventario?error=Producto no encontrado.", status_code=303)

    category_options = products_repo.catalog_options()
    return templates.TemplateResponse(
        request,
        "producto_editar_page.html",
        {
            "request": request,
            "current_page": "inventario",
            "user": username,
            "product": product,
            "category_options": category_options,
        }
    )


@app.post("/producto/{codigo}/editar")
async def actualizar_producto(request: Request, codigo: str):
    """UPDATE: guarda cambios en el producto en MySQL."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    if id_casa is None:
        return RedirectResponse(url="/inventario?error=No se encontró la casa del usuario.", status_code=303)

    form = await read_form(request)
    quantity = form.get("cantidad", "0").strip() or "0"
    expiration = form.get("vence", "").strip()

    producto = products_repo.update_product(codigo, {
        "nombre": form.get("nombre", "").strip() or "Producto sin nombre",
        "categoria": form.get("categoria", "Otros").strip(),
        "subcategoria": form.get("subcategoria", "").strip() or None,
        "presentacion": form.get("presentacion", "").strip() or "Unidad",
        "cantidad": int(quantity),
        "ubicacion": form.get("ubicacion", "").strip(),
        "vence": expiration or None,
    }, id_casa)

    if producto is None:
        return RedirectResponse(url="/inventario?error=Producto no encontrado.", status_code=303)

    return RedirectResponse(url=f"/producto/{codigo}?success=Producto actualizado.", status_code=303)


@app.post("/producto/{codigo}/eliminar")
async def eliminar_producto(request: Request, codigo: str):
    """DELETE: elimina un producto del inventario en MySQL."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    eliminado = products_repo.delete_product(codigo, id_casa) if id_casa is not None else False
    if not eliminado:
        return RedirectResponse(url="/inventario?error=Producto no encontrado.", status_code=303)

    SHOPPING_ITEMS.pop(codigo, None)
    SHOPPING_REMOVED.discard(codigo)

    return RedirectResponse(url="/inventario?success=Producto eliminado.", status_code=303)


@app.get("/alertas")
def alertas(request: Request):

    """Muestra productos con estado no activo (alertas)."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)

    if id_casa is None:
        return RedirectResponse(
            url="/?error=No se encontró la casa del usuario.",
            status_code=303
        )

    products = products_repo.list_products(id_casa)

    alert_products = [
        product for product in products
        if product["estado"] != "Activo"
    ]

    return templates.TemplateResponse(
        request,
        "alertas_page.html",
        {
            "request": request,
            "current_page": "alertas",
            "user": username,
            "alert_products": alert_products
        }
    )


@app.get("/lista-compra")
def lista_compra(request: Request):
    """Muestra todos los productos del inventario en la lista de compra."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    id_casa = current_user_casa(request)
    if id_casa is None:
        return RedirectResponse(url="/?error=No se encontró la casa del usuario.", status_code=303)

    products = current_products(id_casa)
    for product in products:
        if product["codigo"] not in SHOPPING_REMOVED:
            SHOPPING_ITEMS.setdefault(product["codigo"], {"cantidad": 0, "comprado": False})

    shopping_products = [
        {
            **product,
            "compra_cantidad": SHOPPING_ITEMS[product["codigo"]]["cantidad"],
            "comprado": SHOPPING_ITEMS[product["codigo"]]["comprado"],
        }
        for product in products
        if product["codigo"] in SHOPPING_ITEMS and product["codigo"] not in SHOPPING_REMOVED
    ]

    custom_products = [
        {
            "codigo": codigo,
            "nombre": item["nombre"],
            "categoria": item.get("categoria") or "Otros",
            "subcategoria": item.get("subcategoria") or "",
            "presentacion": item.get("unidad") or "Unidad",
            "cantidad": "-",
            "compra_cantidad": item["cantidad"],
            "comprado": item["comprado"],
            "personalizado": True,
        }
        for codigo, item in CUSTOM_SHOPPING_ITEMS.items()
    ]

    all_products = shopping_products + custom_products

    # Agrupar los artículos por categoría para mostrarlos en secciones
    por_categoria: dict[str, list] = {}
    for item in all_products:
        categoria = item.get("categoria") or "Otros"
        por_categoria.setdefault(categoria, []).append(item)

    orden = CATEGORY_ORDER + [c for c in por_categoria if c not in CATEGORY_ORDER]
    shopping_groups = [
        {
            "categoria": categoria,
            "icono": CATEGORY_ICONS.get(categoria, "📦"),
            "productos": por_categoria[categoria],
        }
        for categoria in orden
        if categoria in por_categoria
    ]

    return templates.TemplateResponse(
        request,
        "lista_compra_page.html",
        {
            "request": request,
            "current_page": "lista_compra",
            "user": username,
            "shopping_products": all_products,
            "shopping_groups": shopping_groups,
            "categorias": CATEGORY_ORDER,
        }
    )
@app.get("/movimientos")
def movimientos(request: Request):
    """Muestra los movimientos de la casa del usuario."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)

    if id_casa is None:
        return RedirectResponse(
            url="/?error=No se encontró la casa del usuario.",
            status_code=303
        )

    movements = movimientos_repo.list_movements(id_casa)

    return templates.TemplateResponse(
        request,
        "movimientos_page.html",
        {
            "request": request,
            "current_page": "movimientos",
            "user": username,
            "movements": movements
        }
    )

@app.get("/movimientos/nuevo")
def nuevo_movimiento(request: Request):

    """Muestra el formulario para registrar un movimiento."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)

    if id_casa is None:
        return RedirectResponse(
            url="/?error=No se encontró la casa del usuario.",
            status_code=303
        )

    products = products_repo.list_products(id_casa)

    return templates.TemplateResponse(
        request,
        "movimiento_nuevo.html",
        {
            "request": request,
            "current_page": "movimientos",
            "user": username,
            "products": products
        }
    )

@app.post("/movimientos/nuevo")
async def crear_movimiento(request: Request):

    """Registra un movimiento y actualiza el inventario."""

    username, redirect = require_user(request)

    if redirect:
        return redirect

    id_casa = current_user_casa(request)

    if id_casa is None:
        return RedirectResponse(
            url="/?error=No se encontró la casa del usuario.",
            status_code=303
        )

    form = await read_form(request)

    codigo = form.get("id_producto", "").strip()
    tipo = form.get("tipo_movimiento", "").strip()
    cantidad_texto = form.get("cantidad", "0").strip()

    if not codigo or not tipo or not cantidad_texto:
        return RedirectResponse(
            url="/movimientos/nuevo?error=Completa todos los campos.",
            status_code=303
        )

    try:
        cantidad = int(float(cantidad_texto))
    except ValueError:
        return RedirectResponse(
            url="/movimientos/nuevo?error=La cantidad no es válida.",
            status_code=303
        )

    if cantidad <= 0:
        return RedirectResponse(
            url="/movimientos/nuevo?error=La cantidad debe ser mayor que cero.",
            status_code=303
        )

    if tipo not in ("Entrada", "Consumo", "Descarte"):
        return RedirectResponse(
            url="/movimientos/nuevo?error=Tipo de movimiento no válido.",
            status_code=303
        )

    # Comprobar que el producto pertenece a la casa del usuario
    producto = products_repo.get_product(codigo, id_casa)

    if producto is None:
        return RedirectResponse(
            url="/movimientos/nuevo?error=Producto no encontrado.",
            status_code=303
        )

    # Evitar consumir o descartar más de lo disponible
    if tipo in ("Consumo", "Descarte") and cantidad > producto["cantidad"]:
        return RedirectResponse(
            url="/movimientos/nuevo?error=No hay suficiente cantidad disponible.",
            status_code=303
        )

    # Obtener el ID real del producto
    id_producto = products_repo._codigo_to_id(codigo)

    # Guardar movimiento en MySQL
    movimientos_repo.create_movement(
        id_producto,
        tipo,
        cantidad
    )

    # Calcular nueva cantidad
    if tipo == "Entrada":
        nueva_cantidad = producto["cantidad"] + cantidad
    else:
        nueva_cantidad = producto["cantidad"] - cantidad

    # Actualizar cantidad del producto
    products_repo.update_product(
        codigo,
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

    return RedirectResponse(
        url="/movimientos?success=Movimiento registrado correctamente.",
        status_code=303
    )

@app.post("/lista-compra/agregar")
async def agregar_a_lista_compra(request: Request):
    """Agrega un articulo exclusivo de compra, sin crear un producto de inventario."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    form = await read_form(request)
    name = form.get("nombre_compra", "").strip()
    if name:
        codigo = next_custom_shopping_code()
        try:
            quantity = max(0, int(form.get("cantidad_compra", "1")))
        except ValueError:
            quantity = 1
        CUSTOM_SHOPPING_ITEMS[codigo] = {
            "nombre": name,
            "cantidad": quantity,
            "comprado": False,
            "categoria": form.get("categoria_compra", "Otros").strip() or "Otros",
            "subcategoria": form.get("subcategoria_compra", "").strip(),
            "unidad": form.get("unidad_compra", "Unidad").strip() or "Unidad",
        }

    return RedirectResponse(url="/lista-compra", status_code=303)


@app.post("/lista-compra/{codigo}/actualizar")
async def actualizar_lista_compra(request: Request, codigo: str):
    """Actualiza solo la cantidad o el estado de compra de un producto."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    if codigo not in SHOPPING_ITEMS and codigo not in CUSTOM_SHOPPING_ITEMS:
        return RedirectResponse(url="/lista-compra", status_code=303)

    form = await read_form(request)
    try:
        quantity = max(0, int(form.get("cantidad_compra", "0")))
    except ValueError:
        quantity = 0

    if codigo in CUSTOM_SHOPPING_ITEMS:
        current = CUSTOM_SHOPPING_ITEMS[codigo]
    else:
        current = SHOPPING_ITEMS.setdefault(codigo, {"cantidad": 0, "comprado": False})
    current["cantidad"] = quantity
    if "comprado" in form:
        current["comprado"] = form["comprado"] == "true"

    return RedirectResponse(url="/lista-compra", status_code=303)


@app.post("/lista-compra/{codigo}/eliminar")
async def eliminar_de_lista_compra(request: Request, codigo: str):
    """Quita un producto de la lista sin eliminarlo del inventario."""
    username, redirect = require_user(request)
    if redirect:
        return redirect

    if codigo in CUSTOM_SHOPPING_ITEMS:
        CUSTOM_SHOPPING_ITEMS.pop(codigo, None)
    else:
        SHOPPING_ITEMS.pop(codigo, None)
        SHOPPING_REMOVED.add(codigo)
    return RedirectResponse(url="/lista-compra", status_code=303)


@app.get("/prueba-db")
def prueba_db():
    try:
        conexion = get_connection()
        cursor = conexion.cursor()

        cursor.execute("SELECT 1")
        resultado = cursor.fetchone()

        cursor.close()
        conexion.close()

        return {
            "mensaje": "Conexión exitosa con la base de datos",
            "resultado": resultado[0]
        }

    except Exception as e:
        return {
            "mensaje": "Error al conectar con la base de datos",
            "error": str(e)
        }
