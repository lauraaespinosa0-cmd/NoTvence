"""Endpoints de autenticación por token, usados por la app React Native."""
import hashlib
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import create_access_token
from app.database import get_connection
from app.deps import get_current_user_casa
from app.passwords import hash_password, verify_password_and_update

router = APIRouter(prefix="/auth", tags=["Autenticación"])

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


class RegisterPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1)


class LoginPayload(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class NfcLoginPayload(BaseModel):
    uid_tag: str = Field(min_length=1, max_length=64)
    tag_secret: str = Field(min_length=32, max_length=128)


class NfcTagOut(BaseModel):
    id: int
    uid_tag: str
    nombre: str
    activo: bool
    creado_en: str
    ultimo_uso: str | None = None


class NfcProvisionOut(NfcTagOut):
    # Solo se devuelve una vez; debe escribirse en el tag y no guardarse en claro.
    tag_secret: str


class NfcTagPayload(BaseModel):
    uid_tag: str = Field(min_length=1, max_length=64)
    nombre: str = Field(default="Tag principal", min_length=1, max_length=80)


def _hash_tag_secret(tag_secret: str) -> str:
    return hashlib.sha256(tag_secret.encode("utf-8")).hexdigest()


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload):
    """Registra un usuario y crea automáticamente su casa (misma lógica que /registro)."""
    username = payload.username.strip()
    email = payload.email.strip()
    password = payload.password.strip()

    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Completa usuario, correo y contraseña.")

    if not PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=400,
            detail="La contraseña debe tener mínimo 8 caracteres, incluyendo al menos una letra y un número.",
        )

    conexion = get_connection()
    cursor = conexion.cursor()

    cursor.execute("SELECT id_usuario FROM usuario WHERE correo = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conexion.close()
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado.")

    cursor.execute("SELECT id_usuario FROM usuario WHERE nombre = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conexion.close()
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya está registrado.")

    nombre_casa = f"Casa de {username}"
    cursor.execute("INSERT INTO casa (nombre_hogar) VALUES (%s)", (nombre_casa,))
    id_casa = cursor.lastrowid

    cursor.execute(
        "INSERT INTO usuario (id_casa, nombre, correo, contrasena) VALUES (%s, %s, %s, %s)",
        (id_casa, username, email, hash_password(password)),
    )
    conexion.commit()
    cursor.close()
    conexion.close()

    return AuthOut(access_token=create_access_token(username), username=username)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginPayload):
    """Valida credenciales y devuelve un token de acceso."""
    username = payload.username.strip()
    password = payload.password.strip()

    conexion = get_connection()
    cursor = conexion.cursor()
    try:
        cursor.execute(
            "SELECT id_usuario, nombre, contrasena FROM usuario WHERE nombre = %s",
            (username,),
        )
        usuario = cursor.fetchone()

        if not usuario:
            raise HTTPException(
                status_code=401,
                detail="Usuario o contraseña incorrectos.",
            )

        valid, replacement_hash = verify_password_and_update(password, usuario[2])
        if not valid:
            raise HTTPException(
                status_code=401,
                detail="Usuario o contraseña incorrectos.",
            )

        if replacement_hash:
            cursor.execute(
                "UPDATE usuario SET contrasena = %s WHERE id_usuario = %s",
                (replacement_hash, usuario[0]),
            )
            conexion.commit()
    finally:
        cursor.close()
        conexion.close()

    return AuthOut(access_token=create_access_token(usuario[1]), username=usuario[1])


@router.post("/nfc-login", response_model=AuthOut)
def nfc_login(payload: NfcLoginPayload):
    """Valida un tag registrado y crea la misma sesión JWT del login normal."""
    uid_tag = payload.uid_tag.strip()
    tag_secret = payload.tag_secret.strip()
    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT u.nombre
        FROM casa_nfc n
        JOIN usuario u ON u.id_casa = n.id_casa
        WHERE n.uid_tag = %s
          AND n.token_hash = %s
          AND n.activo = TRUE
        LIMIT 1
        """,
        (uid_tag, _hash_tag_secret(tag_secret)),
    )
    usuario = cursor.fetchone()
    if usuario:
        cursor.execute(
            "UPDATE casa_nfc SET ultimo_uso = CURRENT_TIMESTAMP WHERE uid_tag = %s",
            (uid_tag,),
        )
        conexion.commit()
    cursor.close()
    conexion.close()

    if not usuario:
        raise HTTPException(status_code=401, detail="Tag NFC inválido o revocado.")

    return AuthOut(access_token=create_access_token(usuario[0]), username=usuario[0])


@router.get("/nfc-tags", response_model=list[NfcTagOut])
def list_nfc_tags(user_casa: tuple[str, int] = Depends(get_current_user_casa)):
    """Lista los tags de la casa sin exponer sus secretos."""
    _, id_casa = user_casa
    conexion = get_connection()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, uid_tag, nombre, activo,
               DATE_FORMAT(creado_en, '%%Y-%%m-%%dT%%H:%%i:%%sZ') AS creado_en,
               DATE_FORMAT(ultimo_uso, '%%Y-%%m-%%dT%%H:%%i:%%sZ') AS ultimo_uso
        FROM casa_nfc
        WHERE id_casa = %s
        ORDER BY creado_en DESC
        """,
        (id_casa,),
    )
    tags = cursor.fetchall()
    cursor.close()
    conexion.close()
    return tags


@router.post("/nfc-tags", response_model=NfcProvisionOut, status_code=status.HTTP_201_CREATED)
def provision_nfc_tag(
    payload: NfcTagPayload,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    """Registra un tag y devuelve su secreto para escribirlo físicamente una sola vez."""
    _, id_casa = user_casa
    uid_tag = payload.uid_tag.strip()
    tag_secret = secrets.token_urlsafe(32)
    conexion = get_connection()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO casa_nfc (id_casa, uid_tag, token_hash, nombre)
            VALUES (%s, %s, %s, %s)
            """,
            (id_casa, uid_tag, _hash_tag_secret(tag_secret), payload.nombre.strip()),
        )
        tag_id = cursor.lastrowid
        cursor.execute(
            """
            SELECT DATE_FORMAT(creado_en, '%%Y-%%m-%%dT%%H:%%i:%%sZ') AS creado_en
            FROM casa_nfc
            WHERE id = %s
            """,
            (tag_id,),
        )
        creado = cursor.fetchone()
        conexion.commit()
    except Exception as exc:
        conexion.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise HTTPException(status_code=409, detail="Ese tag ya está registrado.") from exc
        raise
    finally:
        cursor.close()
        conexion.close()

    return NfcProvisionOut(
        id=tag_id,
        uid_tag=uid_tag,
        nombre=payload.nombre.strip(),
        activo=True,
        creado_en=creado["creado_en"],
        ultimo_uso=None,
        tag_secret=tag_secret,
    )


@router.delete("/nfc-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_nfc_tag(
    tag_id: int,
    user_casa: tuple[str, int] = Depends(get_current_user_casa),
):
    """Revoca un tag de la casa sin borrar su registro histórico."""
    _, id_casa = user_casa
    conexion = get_connection()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE casa_nfc SET activo = FALSE WHERE id = %s AND id_casa = %s",
        (tag_id, id_casa),
    )
    updated = cursor.rowcount
    conexion.commit()
    cursor.close()
    conexion.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Tag NFC no encontrado.")
    return None
