"""Punto de entrada.   Ejecutar:  uv run fastapi dev clase4/esqueleto/main.py   →   /docs"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import create_db_and_tables
from routers import auth, feed, posts, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Clase 4", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(feed.router)
