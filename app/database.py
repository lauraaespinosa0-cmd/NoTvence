import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    required = {
        "NOTVENCE_DB_USER": os.getenv("NOTVENCE_DB_USER"),
        "NOTVENCE_DB_PASSWORD": os.getenv("NOTVENCE_DB_PASSWORD"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Faltan variables de conexión MySQL: " + ", ".join(missing)
        )

    try:
        port = int(os.getenv("NOTVENCE_DB_PORT", "3320"))
    except ValueError as exc:
        raise RuntimeError("NOTVENCE_DB_PORT debe ser un número entero.") from exc

    connection_options = {
        "host": os.getenv("NOTVENCE_DB_HOST", "127.0.0.1"),
        "user": required["NOTVENCE_DB_USER"],
        "password": required["NOTVENCE_DB_PASSWORD"],
        "database": os.getenv("NOTVENCE_DB_NAME", "notvence"),
        "port": port,
    }

    ssl_ca = os.getenv("NOTVENCE_DB_SSL_CA")
    if ssl_ca:
        connection_options.update(
            ssl_ca=ssl_ca,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )

    conexion = mysql.connector.connect(**connection_options)

    return conexion