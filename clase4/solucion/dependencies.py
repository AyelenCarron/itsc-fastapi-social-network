"""Lo que reutilizan los routers: sesión, usuario actual y permisos."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from database import get_session
from models import Post, Role, User
from security import read_access_token

SessionDep = Annotated[Session, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ═══════════════ Autenticación: ¿quién eres? → 401 ═══════════════
def credentials_error() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: SessionDep) -> User:    
    user_id = read_access_token(token)
    if user_id is None:
        raise credentials_error()
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ═══════════════ Autorización: ¿qué puedes hacer? → 403 ═══════════════
def is_admin(user: User) -> bool:
    return user.role == Role.ADMIN


def require(allowed: bool) -> None:
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permiso para esto")


# ═══════════════ "Existe o 404" ═══════════════
def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


def get_post_or_404(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post no encontrado")
    return post
