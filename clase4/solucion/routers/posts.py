from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from dependencies import CurrentUser, SessionDep, get_post_or_404, is_admin, require
from models import Like, Post, PostCreate, PostPublic, PostUpdate, PostWithLikes, User, UserPublic

router = APIRouter(prefix="/posts", tags=["posts"])


# ═══════════════ Lectura de posts CON la cuenta de likes ═══════════════
def posts_with_likes():
    """SELECT posts.*, COUNT(likes.user_id)
       FROM posts LEFT JOIN likes ON likes.post_id = posts.id
       GROUP BY posts.id

    LEFT JOIN (isouter=True): los posts SIN likes también aparecen, con 0.
    Con un JOIN común desaparecerían del resultado."""
    return (
        select(Post, func.count(col(Like.user_id)))
        .join(Like, col(Like.post_id) == col(Post.id), isouter=True)
        .group_by(col(Post.id))
    )


def to_post_with_likes(row) -> PostWithLikes:
    post, likes_count = row  # cada fila del SELECT es una tupla (Post, int)
    return PostWithLikes.model_validate(post, update={"likes_count": likes_count})


def get_post_with_likes_or_404(db: Session, post_id: int) -> PostWithLikes:
    row = db.exec(posts_with_likes().where(Post.id == post_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post no encontrado")
    return to_post_with_likes(row)


@router.get("", response_model=list[PostWithLikes])
def read_posts(db: SessionDep, offset: int = 0, limit: Annotated[int, Query(le=100)] = 20):
    stmt = posts_with_likes().order_by(col(Post.created_at).desc()).offset(offset).limit(limit)
    return [to_post_with_likes(row) for row in db.exec(stmt).all()]


@router.get("/{post_id}", response_model=PostWithLikes)
def read_post(post_id: int, db: SessionDep):
    return get_post_with_likes_or_404(db, post_id)


# ═══════════════ CRUD de la clase 2 (sin cambios) ═══════════════
@router.post("", response_model=PostPublic, status_code=201)
def create_post(data: PostCreate, db: SessionDep, current_user: CurrentUser):
    post = Post(**data.model_dump(), author_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.patch("/{post_id}", response_model=PostPublic)
def update_post(post_id: int, data: PostUpdate, db: SessionDep, current_user: CurrentUser):
    post = get_post_or_404(db, post_id)
    require(post.author_id == current_user.id or is_admin(current_user))
    post.sqlmodel_update(data.model_dump(exclude_unset=True))
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: int, db: SessionDep, current_user: CurrentUser):
    post = get_post_or_404(db, post_id)
    require(post.author_id == current_user.id or is_admin(current_user))
    db.delete(post)  # los likes de este post se borran solos: ondelete="CASCADE"
    db.commit()


# ═══════════════ Likes ═══════════════
@router.put("/{post_id}/like", response_model=PostWithLikes)
def like_post(post_id: int, db: SessionDep, current_user: CurrentUser):
    get_post_or_404(db, post_id)
    # db.get con clave COMPUESTA: la tupla va en el orden en que declaraste las primary_key
    if db.get(Like, (current_user.id, post_id)) is None:
        db.add(Like(user_id=current_user.id, post_id=post_id))
        db.commit()
    return get_post_with_likes_or_404(db, post_id)


@router.delete("/{post_id}/like", response_model=PostWithLikes)
def unlike_post(post_id: int, db: SessionDep, current_user: CurrentUser):
    get_post_or_404(db, post_id)
    like = db.get(Like, (current_user.id, post_id))
    if like is not None:
        db.delete(like)
        db.commit()
    return get_post_with_likes_or_404(db, post_id)


@router.get("/{post_id}/likes", response_model=list[UserPublic])
def read_post_likes(
    post_id: int, db: SessionDep, offset: int = 0, limit: Annotated[int, Query(le=100)] = 20
):
    """¿Quiénes le dieron like a este post? (los más recientes primero)"""
    get_post_or_404(db, post_id)
    stmt = (
        select(User)
        .join(Like, col(Like.user_id) == col(User.id))
        .where(Like.post_id == post_id)
        .order_by(col(Like.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return db.exec(stmt).all()
