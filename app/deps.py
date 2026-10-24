"""Dependencias de autenticación compartidas entre las páginas HTML y la API JSON."""
from fastapi import Depends, HTTPException, Request, status

from app.auth import get_bearer_user
from app.database import get_connection


def current_user(request: Request) -> str | None:
    """Obtiene el nombre del usuario desde las cookies, validando que exista en MySQL."""
    username = request.cookies.get("notvence_user")
    if not username:
        return None

    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute("SELECT 1 FROM usuario WHERE nombre = %s", (username,))
    existe = cursor.fetchone()
    cursor.close()
    conexion.close()

    return username if existe else None


def get_user_casa(username: str) -> int | None:
    """Obtiene el id_casa asociado a un usuario."""
    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute("SELECT id_casa FROM usuario WHERE nombre = %s", (username,))
    resultado = cursor.fetchone()
    cursor.close()
    conexion.close()
    return resultado[0] if resultado else None


def get_current_user_casa(username: str = Depends(get_bearer_user)) -> tuple[str, int]:
    """Dependencia para la API JSON (token bearer): exige sesión activa y casa asociada."""
    id_casa = get_user_casa(username)
    if id_casa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la casa del usuario.",
        )
    return username, id_casa
