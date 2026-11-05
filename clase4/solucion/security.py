"""CAJA NEGRA para la clase: hoy usamos estas 4 funciones sin abrirlas."""
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

# En producción define SECRET_KEY en el entorno; este valor es solo para clase.
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

_password_hash = PasswordHash.recommended()  # Argon2


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id), 
            "iat": now, 
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def read_access_token(token: str) -> int | None:
    """Devuelve el id de usuario del token, o None si es inválido o expiró."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])    
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        return None
