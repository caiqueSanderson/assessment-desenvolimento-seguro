from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from database.database import get_session
from main import app


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(test_engine)


def override_get_session():
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session

client = TestClient(app)


def test_criar_consulta_com_sucesso():
    payload = {
        "paciente_id": 1,
        "profissional_id": 10,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
    )

    assert response.status_code == 201

    consulta = response.json()

    assert consulta["id"] is not None
    assert consulta["paciente_id"] == 1
    assert consulta["profissional_id"] == 10
    assert consulta["status"] == "agendada"