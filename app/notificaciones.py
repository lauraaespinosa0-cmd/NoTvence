
"""Envío de notificaciones por correo para NoTvence."""

import base64
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CARPETA = Path(__file__).resolve().parent
CREDENCIALES = CARPETA / "credentials.json"
TOKEN = CARPETA / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


def conectar_gmail():
    """Conecta con la cuenta de Gmail autorizada."""
    credenciales = None

    if not CREDENCIALES.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {CREDENCIALES}"
        )

    if TOKEN.exists() and TOKEN.stat().st_size > 0:
        credenciales = Credentials.from_authorized_user_file(
            str(TOKEN),
            SCOPES,
        )

    if not credenciales or not credenciales.valid:
        if (
            credenciales
            and credenciales.expired
            and credenciales.refresh_token
        ):
            credenciales.refresh(Request())
        else:
            flujo = InstalledAppFlow.from_client_secrets_file(
                str(CREDENCIALES),
                SCOPES,
            )
            credenciales = flujo.run_local_server(port=0)

        TOKEN.write_text(
            credenciales.to_json(),
            encoding="utf-8",
        )

    return build(
        "gmail",
        "v1",
        credentials=credenciales,
    )


def _obtener_datos_alerta(tipo: str) -> dict:
    """Devuelve el asunto y el texto según el tipo de alerta."""
    tipos = {
        "STOCK_BAJO": {
            "asunto": "⚠️ Producto con stock bajo",
            "estado": "Stock bajo",
            "explicacion": (
                "La cantidad disponible alcanzó el límite "
                "mínimo configurado. Revisa tu inventario "
                "y considera incluir el producto en tu "
                "lista de compras."
            ),
            "color": "#d97706",
        },
        "TRES_DIAS": {
            "asunto": "⚠️ Producto próximo a vencer",
            "estado": "Próximo a vencer",
            "explicacion": (
                "El producto vencerá dentro de aproximadamente "
                "tres días. Revisa su etiqueta y planifica "
                "su uso."
            ),
            "color": "#d97706",
        },
        "POR_VENCER": {
            "asunto": "⚠️ Producto próximo a vencer",
            "estado": "Por vencer",
            "explicacion": (
                "La fecha de vencimiento está próxima. "
                "Revisa el producto y planifica su uso."
            ),
            "color": "#d97706",
        },
        "VENCIDO": {
            "asunto": "⚠️ Producto vencido",
            "estado": "Vencido",
            "explicacion": (
                "La fecha de vencimiento ya pasó. "
                "Revisa la etiqueta y las indicaciones "
                "de seguridad antes de decidir qué hacer."
            ),
            "color": "#dc2626",
        },
    }

    tipo_normalizado = str(tipo).strip().upper()

    if tipo_normalizado not in tipos:
        raise ValueError(
            f"Tipo de alerta no reconocido: {tipo}"
        )

    return tipos[tipo_normalizado]


def enviar_aviso(
    destinatario,
    nombre_producto,
    cantidad,
    presentacion,
    fecha_vencimiento,
    tipo,
):
    """
    Envía un correo de alerta por Gmail.

    Tipos aceptados:
    STOCK_BAJO, TRES_DIAS, POR_VENCER y VENCIDO.
    """
    if not destinatario:
        raise ValueError(
            "El destinatario del correo es obligatorio."
        )

    datos = _obtener_datos_alerta(tipo)

    asunto = datos["asunto"]
    estado = datos["estado"]
    explicacion = datos["explicacion"]
    color_estado = datos["color"]

    # La fecha puede ser None para una alerta de stock.
    if isinstance(fecha_vencimiento, date):
        fecha_formateada = fecha_vencimiento.strftime("%d/%m/%Y")
    elif fecha_vencimiento:
        try:
            fecha_formateada = date.fromisoformat(
                str(fecha_vencimiento)
            ).strftime("%d/%m/%Y")
        except ValueError:
            fecha_formateada = str(fecha_vencimiento)
    else:
        fecha_formateada = "No registrada"

    unidad = presentacion or "unidades"
    cantidad_texto = f"{cantidad} {unidad}"

    # Escapar datos variables para insertarlos de forma segura
    # en el HTML del correo.
    nombre_html = escape(str(nombre_producto))
    cantidad_html = escape(cantidad_texto)
    fecha_html = escape(fecha_formateada)
    estado_html = escape(estado)
    explicacion_html = escape(explicacion)
    asunto_html = escape(asunto)

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,
                                      initial-scale=1.0">
        <title>NoTvence - Notificación</title>
    </head>
    <body style="margin:0; padding:24px;
                 background-color:#f3f6f4;
                 font-family:Arial,sans-serif;
                 color:#24332b;">

        <div style="max-width:560px; margin:auto;
                    background:#ffffff; border-radius:14px;
                    overflow:hidden; border:1px solid #e0e8e2;">

            <div style="background:#176b45; color:white;
                        padding:24px; text-align:center;">
                <h1 style="margin:0; font-size:25px;">
                    NoTvence
                </h1>
                <p style="margin:8px 0 0;">
                    Notificación de inventario
                </p>
            </div>

            <div style="padding:26px;">
                <h2 style="font-size:21px; margin-top:0;">
                    {asunto_html}
                </h2>

                <p style="font-size:15px; line-height:1.6;">
                    Hola, tienes un producto que necesita
                    tu atención.
                </p>

                <div style="background:#f7faf8;
                            border:1px solid #e0e8e2;
                            border-radius:10px; padding:18px;
                            line-height:2;">

                    <p style="margin:0;">
                        <strong>Producto:</strong>
                        {nombre_html}
                    </p>

                    <p style="margin:0;">
                        <strong>Cantidad disponible:</strong>
                        {cantidad_html}
                    </p>

                    <p style="margin:0;">
                        <strong>Fecha de vencimiento:</strong>
                        {fecha_html}
                    </p>

                    <p style="margin:0;">
                        <strong>Alerta:</strong>
                        <span style="color:{color_estado};
                                     font-weight:bold;">
                            {estado_html}
                        </span>
                    </p>
                </div>

                <p style="font-size:15px; line-height:1.6;
                          margin-top:22px;">
                    {explicacion_html}
                </p>

                <p style="font-size:12px; color:#6b7280;
                          margin-top:24px; text-align:center;">
                    Este es un mensaje automático de NoTvence.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    texto_plano = (
        "NoTvence - Notificación de inventario\n\n"
        f"{asunto}\n\n"
        f"Producto: {nombre_producto}\n"
        f"Cantidad disponible: {cantidad_texto}\n"
        f"Fecha de vencimiento: {fecha_formateada}\n"
        f"Alerta: {estado}\n\n"
        f"{explicacion}\n\n"
        "Mensaje automático de NoTvence."
    )

    mensaje = MIMEMultipart("alternative")
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto

    mensaje.attach(
        MIMEText(texto_plano, "plain", "utf-8")
    )
    mensaje.attach(
        MIMEText(html, "html", "utf-8")
    )

    contenido = base64.urlsafe_b64encode(
        mensaje.as_bytes()
    ).decode("utf-8")

    servicio = conectar_gmail()

    resultado = servicio.users().messages().send(
        userId="me",
        body={"raw": contenido},
    ).execute()

    return resultado
