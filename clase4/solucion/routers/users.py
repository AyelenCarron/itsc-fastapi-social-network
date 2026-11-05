from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from dependencies import CurrentUser, SessionDep, get_user_or_404
from models import Follow, Like, Post, PostPublic, User, UserProfile, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


# ═══════════════ Perfil con contadores ═══════════════
def to_profile(db: Session, user: User) -> UserProfile:
    # Dos conteos en direcciones OPUESTAS sobre la misma tabla:
    followers = db.exec(
        select(func.count()).select_from(Follow).where(Follow.followed_id == user.id)
    ).one()  # filas donde user es el SEGUIDO
    following = db.exec(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)
    ).one()  # filas donde user es el SEGUIDOR
    return UserProfile.model_validate(
        user, update={"followers_count": followers, "following_count": following}
    )


@router.get("/{user_id}", response_model=UserProfile)
def read_user(user_id: int, db: SessionDep):
    return to_profile(db, get_user_or_404(db, user_id))


@router.get("/{user_id}/posts", response_model=list[PostPublic])
def read_user_posts(user_id: int, db: SessionDep):
    return get_user_or_404(db, user_id).posts


@router.get("/{user_id}/likes", response_model=list[PostPublic])
def read_user_likes(
    user_id: int, db: SessionDep, offset: int = 0, limit: Annotated[int, Query(le=100)] = 20
):
    """Los posts a los que este usuario le dio like (el más reciente primero)."""
    get_user_or_404(db, user_id)
    stmt = (
        select(Post)
        .join(Like, col(Like.post_id) == col(Post.id))
        .where(Like.user_id == user_id)
        .order_by(col(Like.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return db.exec(stmt).all()


# ═══════════════ Seguir / dejar de seguir ═══════════════
@router.put("/{user_id}/follow", response_model=UserProfile)
def follow_user(user_id: int, db: SessionDep, current_user: CurrentUser):
    target = get_user_or_404(db, user_id)
    if target.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes seguirte a ti mismo")
    if db.get(Follow, (current_user.id, user_id)) is None:  # orden de las PK: (follower, followed)
        db.add(Follow(follower_id=current_user.id, followed_id=user_id))
        db.commit()
    return to_profile(db, target)


@router.delete("/{user_id}/follow", response_model=UserProfile)
def unfollow_user(user_id: int, db: SessionDep, current_user: CurrentUser):
    target = get_user_or_404(db, user_id)
    follow = db.get(Follow, (current_user.id, user_id))
    if follow is not None:
        db.delete(follow)
        db.commit()
    return to_profile(db, target)


# ═══════════════ Listas: followers vs following ═══════════════
# Follow tiene DOS claves foráneas hacia users, así que el JOIN necesita la condición explícita:
#   .join(Follow, <cuál columna de Follow se une con User.id>)
# followers de X = usuarios que lo SIGUEN   → los follower_id de las filas donde followed_id == X
# following de X = usuarios a los que SIGUE → los followed_id de las filas donde follower_id == X
@router.get("/{user_id}/followers", response_model=list[UserPublic])
def read_followers(
    user_id: int, db: SessionDep, offset: int = 0, limit: Annotated[int, Query(le=100)] = 20
):
    get_user_or_404(db, user_id)
    stmt = (
        select(User)
        .join(Follow, col(Follow.follower_id) == col(User.id))
        .where(Follow.followed_id == user_id)
        .order_by(col(Follow.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return db.exec(stmt).all()


@router.get("/{user_id}/following", response_model=list[UserPublic])
def read_following(
    user_id: int, db: SessionDep, offset: int = 0, limit: Annotated[int, Query(le=100)] = 20
):
    get_user_or_404(db, user_id)
    stmt = (
        select(User)
        .join(Follow, col(Follow.followed_id) == col(User.id))
        .where(Follow.follower_id == user_id)
        .order_by(col(Follow.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return db.exec(stmt).all()
