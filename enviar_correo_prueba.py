import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CARPETA = Path(__file__).resolve().parent
CREDENCIALES = CARPETA / "credentials.json"
TOKEN = CARPETA / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def conectar_gmail():
    credenciales = None

    if not CREDENCIALES.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {CREDENCIALES}"
        )

    if TOKEN.exists() and TOKEN.stat().st_size > 0:
        credenciales = Credentials.from_authorized_user_file(
            str(TOKEN), SCOPES
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
                str(CREDENCIALES), SCOPES
            )
            credenciales = flujo.run_local_server(port=0)

        TOKEN.write_text(
            credenciales.to_json(),
            encoding="utf-8"
        )

    return build("gmail", "v1", credentials=credenciales)


def enviar_correo(destinatario):
    servicio = conectar_gmail()

    mensaje = MIMEText(
        "¡Hola! Este es un correo de prueba de NoTvence. "
        "La conexión entre Python y Gmail funciona."
    )

    mensaje["to"] = destinatario
    mensaje["subject"] = "Prueba de notificaciones - NoTvence"

    contenido = base64.urlsafe_b64encode(
        mensaje.as_bytes()
    ).decode("utf-8")

    servicio.users().messages().send(
        userId="me",
        body={"raw": contenido}
    ).execute()

    print("Correo enviado correctamente.")


if __name__ == "__main__":
    destino = input(
        "Escribe el correo que recibirá la prueba: "
    ).strip()

    if "@" not in destino or "." not in destino.split("@")[-1]:
        print("Escribe una dirección de correo válida.")
    else:
        try:
            enviar_correo(destino)
        except Exception as error:
            print(f"No se pudo enviar el correo: {error}")
