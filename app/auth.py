"""Autenticación por token (JWT) para la API JSON usada por la app React Native.

Las páginas HTML (Jinja2) siguen usando la cookie de sesión definida en app/deps.py;
este módulo es independiente y solo lo consume la API bajo /api.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException, status

SECRET_KEY = os.environ.get("NOTVENCE_JWT_SECRET", "notvence-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 30  # 30 días: pensado para sesiones móviles de larga duración


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def get_bearer_user(authorization: str | None = Header(default=None)) -> str:
    """Dependencia FastAPI: exige un header 'Authorization: Bearer <token>' válido."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación.",
        )

    token = authorization.split(" ", 1)[1].strip()
    username = decode_access_token(token)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )

    return username
