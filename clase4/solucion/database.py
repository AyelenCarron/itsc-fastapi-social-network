import sqlite3
from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

engine = create_engine("sqlite:///./clase4.db", connect_args={"check_same_thread": False})


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_conn, _):
    # SQLite ignora las claves foráneas (y ON DELETE CASCADE) salvo que se active.
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
