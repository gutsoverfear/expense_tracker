import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, SessionLocal, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    SessionLocal.configure(bind=engine)

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    SessionLocal.configure(bind=None)
    Base.metadata.drop_all(engine)


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    assert response.status_code == 201
    login = client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    assert login.status_code == 200
    return login.json()["access_token"]