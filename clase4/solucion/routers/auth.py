"""Registro, login y 'quién soy'."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from dependencies import CurrentUser, SessionDep, credentials_error
from models import Token, User, UserCreate, UserMe
from security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserMe, status_code=201)
def register(data: UserCreate, db: SessionDep):    
    existente = db.exec(select(User).where(User.username == data.username)).first()
    if existente:
        raise HTTPException(status.HTTP_409_CONFLICT, "Usuario ya existente")
    user = User(username=data.username, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: SessionDep):    
    user = db.exec(select(User).where(User.username == form.username)).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise credentials_error()
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserMe)
def me(current_user: CurrentUser):  # ya resuelto: funciona cuando hagas el TODO 4
    return current_user
