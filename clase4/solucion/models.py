"""Tablas (table=True) y schemas de la API."""
import enum
from datetime import datetime, timezone
from typing import Annotated

from pydantic import StringConstraints
from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


# ═══════════════ Usuarios ═══════════════
class UserBase(SQLModel):
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)


class User(UserBase, table=True):
    __tablename__ = "users"
    
    id: int | None = Field(default=None, primary_key=True)
    hashed_password:str
    role: Role = Field(default=Role.USER)
    posts: list["Post"] = Relationship(back_populates="author")


class UserCreate(UserBase):  # ENTRA al registrarse: tiene password, NO tiene role
    password: Password


class UserPublic(UserBase):  # SALE: vista pública
    id: int


class UserMe(UserPublic):  # SALE: vista privada, solo para el propio usuario
    role: Role


class UserProfile(UserPublic):  # SALE: el usuario + sus contadores (se calculan, no se guardan)
    followers_count: int  # cuántos lo siguen a él
    following_count: int  # a cuántos sigue él


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# ═══════════════ Posts ═══════════════
class PostBase(SQLModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class Post(PostBase, table=True):
    __tablename__ = "posts"

    id: int | None = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=utcnow)
    author: User = Relationship(back_populates="posts")


class PostCreate(PostBase):    
    pass


class PostUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=2000)


class PostPublic(PostBase):
    id: int
    author_id: int
    created_at: datetime


class PostWithLikes(PostPublic):  # SALE: el post + cuántos likes tiene (se calcula, no se guarda)
    likes_count: int


# ═══════════════ Likes ═══════════════
class Like(SQLModel, table=True):
    """Tabla de ENLACE: una fila = "este usuario le dio like a este post".
    La clave primaria es COMPUESTA (user_id, post_id): la base de datos misma
    impide que el mismo usuario dé dos likes al mismo post."""

    __tablename__ = "likes"

    user_id: int = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    post_id: int = Field(foreign_key="posts.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=utcnow)


# ═══════════════ Follows ═══════════════
class Follow(SQLModel, table=True):
    """Tabla de ENLACE de users CONSIGO MISMA. Una fila = "follower sigue a followed".
    Ojo con la dirección: follower_id es QUIEN sigue, followed_id es A QUIÉN sigue."""

    __tablename__ = "follows"
    # Defensa en profundidad: la API ya rechaza seguirse a uno mismo, pero la base lo garantiza igual.
    __table_args__ = (CheckConstraint("follower_id != followed_id", name="no_self_follow"),)

    follower_id: int = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    followed_id: int = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=utcnow)
