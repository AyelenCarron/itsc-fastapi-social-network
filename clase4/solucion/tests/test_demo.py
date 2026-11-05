"""TODO 8: ejecuta  pytest -q  ahora (verás rojo) y otra vez al terminar los TODO 1-7 (verde).
TODO 9: al final de este archivo hay un test para que lo escribas tú."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database import get_session
from main import app


@pytest.fixture()
def engine():
    # Base de datos en memoria: cada test empieza de cero y no toca clase4.db
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def client(engine):
    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)  # sin `with`: no ejecuta el lifespan (que usaría la BD real)
    app.dependency_overrides.clear()


@pytest.fixture()
def sql_log(engine):
    """Lista con cada sentencia SQL que se ejecuta: sirve para contar consultas."""
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    yield statements
    event.remove(engine, "before_cursor_execute", record)


def register_and_login(client, username: str) -> dict:
    body = {"username": username, "password": "supersecreta123"}
    assert client.post("/auth/register", json=body).status_code == 201
    r = client.post("/auth/login", data=body)  # el login usa formulario, no JSON
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def user_id(client, headers) -> int:
    return client.get("/auth/me", headers=headers).json()["id"]


def new_post(client, headers, title="Hola") -> int:
    r = client.post("/posts", json={"title": title, "content": "contenido"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


# ── Regresión: clases 2 y 3 siguen funcionando ─────────────────────────────────
def test_previous_classes_still_work(client):
    alice, bob = register_and_login(client, "alice"), register_and_login(client, "bob")
    post_id = new_post(client, alice)

    assert client.post("/posts", json={"title": "x", "content": "y"}).status_code == 401
    assert client.delete(f"/posts/{post_id}", headers=bob).status_code == 403
    assert client.put(f"/posts/{post_id}/like", headers=bob).json()["likes_count"] == 1


# ── Follows ────────────────────────────────────────────────────────────────────
def test_follow_updates_both_counters_and_is_idempotent(client):
    alice, bob = register_and_login(client, "alice"), register_and_login(client, "bob")
    alice_id, bob_id = user_id(client, alice), user_id(client, bob)

    r = client.put(f"/users/{bob_id}/follow", headers=alice)  # alice sigue a bob
    assert r.status_code == 200
    assert (r.json()["followers_count"], r.json()["following_count"]) == (1, 0)  # bob

    assert client.put(f"/users/{bob_id}/follow", headers=alice).json()["followers_count"] == 1

    alice_profile = client.get(f"/users/{alice_id}").json()
    assert (alice_profile["followers_count"], alice_profile["following_count"]) == (0, 1)


def test_cannot_follow_yourself(client, engine):
    from models import Follow

    alice = register_and_login(client, "alice")
    alice_id = user_id(client, alice)

    assert client.put(f"/users/{alice_id}/follow", headers=alice).status_code == 400

    # ...y aunque alguien se saltee la API, la base de datos también lo rechaza
    with Session(engine) as db:
        db.add(Follow(follower_id=alice_id, followed_id=alice_id))
        with pytest.raises(IntegrityError):
            db.commit()


def test_follow_errors_401_and_404(client):
    alice = register_and_login(client, "alice")
    bob_id = user_id(client, register_and_login(client, "bob"))

    assert client.put(f"/users/{bob_id}/follow").status_code == 401
    assert client.put("/users/9999/follow", headers=alice).status_code == 404
    assert client.delete("/users/9999/follow", headers=alice).status_code == 404
    assert client.get("/users/9999/followers").status_code == 404
    assert client.get("/users/9999/following").status_code == 404


def test_unfollow_and_unfollow_again(client):
    alice, bob = register_and_login(client, "alice"), register_and_login(client, "bob")
    bob_id = user_id(client, bob)
    client.put(f"/users/{bob_id}/follow", headers=alice)

    assert client.delete(f"/users/{bob_id}/follow", headers=alice).json()["followers_count"] == 0
    assert client.delete(f"/users/{bob_id}/follow", headers=alice).status_code == 200  # idempotente


def test_followers_and_following_are_not_mixed_up(client):
    # TODO 9 (resuelto): el test que protege del error clásico (listas invertidas)
    # alice sigue a bob y a carol; dave sigue a alice
    alice, dave = register_and_login(client, "alice"), register_and_login(client, "dave")
    bob_id = user_id(client, register_and_login(client, "bob"))
    carol_id = user_id(client, register_and_login(client, "carol"))
    alice_id = user_id(client, alice)
    client.put(f"/users/{bob_id}/follow", headers=alice)
    client.put(f"/users/{carol_id}/follow", headers=alice)
    client.put(f"/users/{alice_id}/follow", headers=dave)

    def names(path):
        return sorted(u["username"] for u in client.get(path).json())

    assert names(f"/users/{alice_id}/following") == ["bob", "carol"]
    assert names(f"/users/{alice_id}/followers") == ["dave"]
    assert names(f"/users/{bob_id}/followers") == ["alice"]
    assert names(f"/users/{bob_id}/following") == []


# ── Feed ───────────────────────────────────────────────────────────────────────
def test_feed_only_has_posts_from_followed_users_and_updates_on_unfollow(client):
    alice, bob = register_and_login(client, "alice"), register_and_login(client, "bob")
    carol = register_and_login(client, "carol")
    bob_id = user_id(client, bob)
    own = new_post(client, alice, "propio")
    from_bob = new_post(client, bob, "de bob")
    new_post(client, carol, "de carol")  # alice no sigue a carol
    assert client.get("/feed", headers=alice).json() == []  # todavía no sigue a nadie

    client.put(f"/users/{bob_id}/follow", headers=alice)
    client.put(f"/posts/{from_bob}/like", headers=carol)
    feed = client.get("/feed", headers=alice).json()
    assert [p["id"] for p in feed] == [from_bob]
    assert own not in [p["id"] for p in feed]
    assert feed[0]["likes_count"] == 1  # el feed reutiliza la consulta con likes

    client.delete(f"/users/{bob_id}/follow", headers=alice)
    assert client.get("/feed", headers=alice).json() == []


def test_feed_requires_token(client):
    assert client.get("/feed").status_code == 401


def test_feed_query_count_does_not_grow_with_followed_users(client, sql_log):
    # Detector de N+1: seguir a 1 persona o a 10 debe costar la MISMA cantidad de consultas.
    authors = []
    for i in range(10):
        h = register_and_login(client, f"autor{i}")
        new_post(client, h, f"post {i}")
        authors.append(user_id(client, h))
    few, many = register_and_login(client, "pocos"), register_and_login(client, "muchos")
    client.put(f"/users/{authors[0]}/follow", headers=few)
    for a in authors:
        client.put(f"/users/{a}/follow", headers=many)

    sql_log.clear()
    assert len(client.get("/feed", headers=few).json()) == 1
    queries_for_one = len(sql_log)

    sql_log.clear()
    assert len(client.get("/feed", headers=many).json()) == 10
    assert len(sql_log) == queries_for_one


def test_unfollow_then_refollow_keeps_a_single_row(client, engine):
    # seguir, dejar de seguir y volver a seguir deja UNA sola fila
    from models import Follow
    from sqlmodel import select

    alice, bob = register_and_login(client, "alice"), register_and_login(client, "bob")
    bob_id = user_id(client, bob)
    for _ in range(2):
        client.put(f"/users/{bob_id}/follow", headers=alice)
        client.put(f"/users/{bob_id}/follow", headers=alice)
        client.delete(f"/users/{bob_id}/follow", headers=alice)
    client.put(f"/users/{bob_id}/follow", headers=alice)

    with Session(engine) as db:
        assert len(db.exec(select(Follow)).all()) == 1
