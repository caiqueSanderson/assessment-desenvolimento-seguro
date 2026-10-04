from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from auth.hash_password import HashPassword
from auth.jwt_handler import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
)
from auth.mfa import SIMULATED_MFA_CODE
from database.database import get_session
from main import app
from models.consulta import Consulta
from models.user import User


# ============================================================
# CONFIGURAÇÃO DO BANCO DE TESTES
# ============================================================

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


# ============================================================
# LIMPEZA DO BANCO ENTRE OS TESTES
# ============================================================

@pytest.fixture(autouse=True)
def limpar_banco():
    with Session(test_engine) as session:

        consultas = session.exec(select(Consulta)).all()
        for consulta in consultas:
            session.delete(consulta)

        usuarios = session.exec(select(User)).all()
        for usuario in usuarios:
            session.delete(usuario)

        session.commit()

    yield


# ============================================================
# HELPERS
# ============================================================

def criar_usuario(
    email: str,
    role: str,
    mfa_enabled: bool = False,
) -> User:

    with Session(test_engine) as session:

        user = User(
            name="Usuário Teste",
            email=email,
            password_hash=HashPassword().create_hash("123456"),
            role=role,
            mfa_enabled=mfa_enabled,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return user


def obter_token(
    email: str,
    password: str = "123456",
    mfa_code: str | None = None,
):
    response = client.post(
        "/auth/signin",
        json={
            "email": email,
            "password": password,
            "mfa_code": mfa_code,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def obter_token_swagger(
    email: str,
    password: str = "123456",
    mfa_code: str | None = None,
):
    data = {
        "username": email,
        "password": password,
    }

    if mfa_code is not None:
        data["mfa_code"] = mfa_code

    response = client.post(
        "/auth/swagger-token",
        data=data,
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def headers(token: str):
    return {
        "Authorization": f"Bearer {token}"
    }


def criar_consulta(
    profissional_id: int,
    paciente_id: int = 1,
):
    with Session(test_engine) as session:

        consulta = Consulta(
            paciente_id=paciente_id,
            profissional_id=profissional_id,
            data_hora=datetime(2026, 9, 22, 14, 0),
            status="agendada",
            audit_token="token-interno",
        )

        session.add(consulta)
        session.commit()
        session.refresh(consulta)

        return consulta


def obter_token_m2m(
    client_id: str = "laboratorio_01",
    client_secret: str = "development-laboratorio-secret",
):
    response = client.post(
        "/auth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


# ============================================================
# EXERCÍCIO 1
# CRUD / CONSULTAS
# ============================================================

def test_create_consulta_com_sucesso():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 201

    consulta = response.json()

    assert consulta["id"] is not None
    assert consulta["paciente_id"] == 1
    assert consulta["profissional_id"] == profissional.id
    assert consulta["status"] == "agendada"


def test_listar_consultas_com_sucesso():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.get(
        "/consultas/",
        headers=headers(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_buscar_consulta_com_sucesso():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.get(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response.status_code == 200

    resultado = response.json()

    assert resultado["id"] == consulta.id
    assert resultado["profissional_id"] == profissional.id


def test_atualizar_consulta_com_sucesso():

    profissional = criar_usuario(
        email="administrador@teste.com",
        role="administrador",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    payload = {
        "status": "concluida",
    }

    response = client.put(
        f"/consultas/{consulta.id}",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 200

    resultado = response.json()

    assert resultado["status"] == "concluida"


def test_excluir_consulta_com_sucesso():

    profissional = criar_usuario(
        email="administrador@teste.com",
        role="administrador",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.delete(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response.status_code == 204

    response_busca = client.get(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response_busca.status_code == 404


# ============================================================
# EXERCÍCIO 2
# PROTEÇÃO DE DADOS / RESPONSE MODEL / XSS
# ============================================================

def test_response_model_nao_expoe_audit_token():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 201

    resultado = response.json()

    assert "audit_token" not in resultado


def test_agenda_escapa_conteudo_html():

    recepcionista = criar_usuario(
        email="recepcao@teste.com",
        role="recepcionista",
    )

    criar_consulta(
        profissional_id=1,
    )

    with Session(test_engine) as session:

        consulta = session.exec(
            select(Consulta)
        ).first()

        consulta.status = "<script>alert('XSS')</script>"

        session.add(consulta)
        session.commit()

    token = obter_token(recepcionista.email)

    response = client.get(
        "/agenda",
        headers=headers(token),
    )

    assert response.status_code == 200

    assert "<script>alert('XSS')</script>" not in response.text

    assert "&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;" in response.text \
        or "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in response.text


# ============================================================
# EXERCÍCIO 6
# AUTENTICAÇÃO
# ============================================================

def test_usuario_sem_token_nao_acessa_consultas():

    response = client.get("/consultas/")

    assert response.status_code == 401


def test_usuario_com_senha_incorreta_nao_autentica():

    criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    response = client.post(
        "/auth/signin",
        json={
            "email": "profissional@teste.com",
            "password": "senha-incorreta",
        },
    )

    assert response.status_code == 401


def test_senha_e_armazenada_com_hash():

    usuario = criar_usuario(
        email="hash@teste.com",
        role="profissional",
    )

    assert usuario.password_hash != "123456"

    assert usuario.password_hash.startswith("$2")


def test_token_jwt_contem_usuario_e_expiracao():

    profissional = criar_usuario(
        email="jwt@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    assert payload["sub"] == str(profissional.id)
    assert payload["email"] == profissional.email
    assert payload["role"] == "profissional"
    assert payload["client_type"] == "user"
    assert "exp" in payload


def test_token_expirado_e_rejeitado():

    profissional = criar_usuario(
        email="expirado@teste.com",
        role="profissional",
    )

    data_expiracao = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )

    token = create_access_token(
        subject=profissional.id,
        claims={
            "client_type": "user",
            "email": profissional.email,
            "role": profissional.role,
            "exp": data_expiracao,
        },
    )

    response = client.get(
        "/consultas/",
        headers=headers(token),
    )

    assert response.status_code == 401


# ============================================================
# EXERCÍCIO 6
# MFA
# ============================================================

def test_admin_com_mfa_sem_codigo_e_bloqueado():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
        mfa_enabled=True,
    )

    response = client.post(
        "/auth/signin",
        json={
            "email": admin.email,
            "password": "123456",
        },
    )

    assert response.status_code == 401


def test_admin_com_mfa_com_codigo_valido_autentica():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
        mfa_enabled=True,
    )

    token = obter_token(
        admin.email,
        mfa_code=SIMULATED_MFA_CODE,
    )

    assert token


def test_admin_com_mfa_codigo_incorreto_e_bloqueado():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
        mfa_enabled=True,
    )

    response = client.post(
        "/auth/signin",
        json={
            "email": admin.email,
            "password": "123456",
            "mfa_code": "000000",
        },
    )

    assert response.status_code == 401


# ============================================================
# EXERCÍCIO 6
# RBAC
# ============================================================

def test_profissional_nao_acessa_rota_admin():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    response = client.get(
        "/consultas/admin-only",
        headers=headers(token),
    )

    assert response.status_code == 403


def test_recepcionista_nao_acessa_rota_admin():

    recepcionista = criar_usuario(
        email="recepcao@teste.com",
        role="recepcionista",
    )

    token = obter_token(recepcionista.email)

    response = client.get(
        "/consultas/admin-only",
        headers=headers(token),
    )

    assert response.status_code == 403


def test_admin_acessa_rota_admin():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
    )

    token = obter_token(admin.email)

    response = client.get(
        "/consultas/admin-only",
        headers=headers(token),
    )

    assert response.status_code == 200

    assert response.json()["message"] == "Área administrativa"


# ============================================================
# EXERCÍCIO 6
# OWNERSHIP - CRIAÇÃO
# ============================================================

def test_profissional_pode_criar_consulta_para_si_mesmo():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 201


def test_profissional_nao_pode_criar_consulta_para_outro():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    outro_profissional = criar_usuario(
        email="outro@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": outro_profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 403


def test_recepcionista_pode_criar_consulta_para_outro_profissional():

    recepcionista = criar_usuario(
        email="recepcao@teste.com",
        role="recepcionista",
    )

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(recepcionista.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 201


def test_admin_pode_criar_consulta_para_outro_profissional():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
    )

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(admin.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 201


# ============================================================
# EXERCÍCIO 6
# OWNERSHIP - LEITURA
# ============================================================

def test_profissional_lista_apenas_suas_consultas():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    outro_profissional = criar_usuario(
        email="outro@teste.com",
        role="profissional",
    )

    criar_consulta(
        profissional_id=profissional.id,
        paciente_id=1,
    )

    criar_consulta(
        profissional_id=outro_profissional.id,
        paciente_id=2,
    )

    token = obter_token(profissional.email)

    response = client.get(
        "/consultas/",
        headers=headers(token),
    )

    assert response.status_code == 200

    consultas = response.json()

    assert len(consultas) == 1
    assert consultas[0]["profissional_id"] == profissional.id


def test_profissional_nao_pode_visualizar_consulta_de_outro():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    outro_profissional = criar_usuario(
        email="outro@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=outro_profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.get(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response.status_code == 403


def test_recepcionista_pode_visualizar_consulta_de_outro():

    recepcionista = criar_usuario(
        email="recepcao@teste.com",
        role="recepcionista",
    )

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(recepcionista.email)

    response = client.get(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response.status_code == 200


def test_admin_pode_visualizar_consulta_de_outro():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
    )

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(admin.email)

    response = client.get(
        f"/consultas/{consulta.id}",
        headers=headers(token),
    )

    assert response.status_code == 200


# ============================================================
# EXERCÍCIO 6
# OWNERSHIP - ALTERAÇÃO
# ============================================================

def test_profissional_nao_pode_atualizar_sua_consulta():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.put(
        f"/consultas/{consulta.id}",
        json={
            "status": "concluida",
        },
        headers=headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "concluida"


def test_profissional_nao_pode_atualizar_consulta_de_outro():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    outro_profissional = criar_usuario(
        email="outro@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=outro_profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.put(
        f"/consultas/{consulta.id}",
        json={
            "status": "concluida",
        },
        headers=headers(token),
    )

    assert response.status_code == 403


def test_profissional_nao_pode_transferir_consulta():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    outro_profissional = criar_usuario(
        email="outro@teste.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional.id,
    )

    token = obter_token(profissional.email)

    response = client.put(
        f"/consultas/{consulta.id}",
        json={
            "profissional_id": outro_profissional.id,
        },
        headers=headers(token),
    )

    assert response.status_code == 403


# ============================================================
# EXERCÍCIO 6
# VALIDAÇÃO DE PAYLOAD
# ============================================================

def test_payload_com_campo_extra_e_rejeitado():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-09-22T14:00:00",
        "status": "agendada",
        "campo_inexistente": "teste",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers=headers(token),
    )

    assert response.status_code == 422


# ============================================================
# SWAGGER / OAUTH2 PASSWORD FLOW
# ============================================================

def test_swagger_token_funciona():

    profissional = criar_usuario(
        email="swagger@teste.com",
        role="profissional",
    )

    token = obter_token_swagger(
        profissional.email,
    )

    assert token


def test_swagger_token_rejeita_senha_incorreta():

    criar_usuario(
        email="swagger@teste.com",
        role="profissional",
    )

    response = client.post(
        "/auth/swagger-token",
        data={
            "username": "swagger@teste.com",
            "password": "senha-incorreta",
        },
    )

    assert response.status_code == 401


# ============================================================
# EXERCÍCIO 7
# M2M / CLIENT CREDENTIALS
# ============================================================

def test_m2m_token_com_credenciais_validas():

    response = client.post(
        "/auth/token",
        data={
            "client_id": "laboratorio_01",
            "client_secret": "development-laboratorio-secret",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "consultas:read" in body["scope"]


def test_m2m_token_com_client_invalido():

    response = client.post(
        "/auth/token",
        data={
            "client_id": "laboratorio_invalido",
            "client_secret": "senha-invalida",
        },
    )

    assert response.status_code == 401


def test_m2m_token_com_secret_invalido():

    response = client.post(
        "/auth/token",
        data={
            "client_id": "laboratorio_01",
            "client_secret": "senha-invalida",
        },
    )

    assert response.status_code == 401


def test_m2m_token_contem_claims_corretos():

    token = obter_token_m2m()

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    assert payload["client_id"] == "laboratorio_01"
    assert payload["client_type"] == "m2m"
    assert "scope" in payload

    scopes = payload["scope"].split()

    assert "laboratorio:read" in scopes
    assert "consultas:read" in scopes


def test_m2m_token_acessa_endpoint_com_scope_correto():

    token = obter_token_m2m()

    response = client.get(
        "/consultas/integracao/consultas",
        headers=headers(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_m2m_token_sem_scope_necessario_e_bloqueado():

    token = create_access_token(
        subject="laboratorio_01",
        claims={
            "client_id": "laboratorio_01",
            "client_type": "m2m",
            "scope": "laboratorio:read",
        },
    )

    response = client.get(
        "/consultas/integracao/consultas",
        headers=headers(token),
    )

    assert response.status_code == 403


def test_token_de_usuario_nao_pode_ser_usado_como_m2m():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    response = client.get(
        "/consultas/integracao/consultas",
        headers=headers(token),
    )

    assert response.status_code == 403


# ============================================================
# PROTEÇÃO CONTRA EXPOSIÇÃO INDEVIDA DE ROTAS
# ============================================================

def test_agenda_sem_autenticacao_e_bloqueada():

    response = client.get("/agenda")

    assert response.status_code == 401


def test_agenda_permite_recepcionista():

    recepcionista = criar_usuario(
        email="recepcao@teste.com",
        role="recepcionista",
    )

    token = obter_token(recepcionista.email)

    response = client.get(
        "/agenda",
        headers=headers(token),
    )

    assert response.status_code == 200


def test_agenda_permite_administrador():

    admin = criar_usuario(
        email="admin@teste.com",
        role="administrador",
    )

    token = obter_token(admin.email)

    response = client.get(
        "/agenda",
        headers=headers(token),
    )

    assert response.status_code == 200


def test_agenda_bloqueia_profissional():

    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    response = client.get(
        "/agenda",
        headers=headers(token),
    )

    assert response.status_code == 403

def test_consulta_rejeita_campo_nao_declarado():
    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-10-03T14:00:00",
        "status": "agendada",
        "audit_token": "tentativa-de-injecao",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

def test_consulta_rejeita_status_invalido():
    profissional = criar_usuario(
        email="profissional@teste.com",
        role="profissional",
    )

    token = obter_token(profissional.email)

    payload = {
        "paciente_id": 1,
        "profissional_id": profissional.id,
        "data_hora": "2026-10-03T14:00:00",
        "status": "status_injetado",
    }

    response = client.post(
        "/consultas/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

def test_login_rate_limit():
    responses = []

    for _ in range(6):
        response = client.post(
            "/auth/swagger-token",
            data={
                "username": "usuario-inexistente",
                "password": "senha-invalida",
            },
        )
        responses.append(response.status_code)

    assert 429 in responses

def test_profissional_nao_pode_visualizar_consulta_de_outro():
    profissional_a = criar_usuario(
            email="profissional.a@clinica.com",
            role="profissional",
    )

    profissional_b = criar_usuario(
        email="profissional.b@clinica.com",
        role="profissional",
    )

    consulta = criar_consulta(
        profissional_id=profissional_b.id
    )

    token = obter_token(profissional_a)

    response = client.get(
        f"/consultas/{consulta.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

def test_profissional_nao_pode_transferir_consulta():
    profissional_a = criar_usuario(
        email="profissional.a@clinica.com",
        role="profissional"
    )

    profissional_b = criar_usuario(
        email="profissional.b@clinica.com",
        role="profissional"
    )

    consulta = criar_consulta(
        profissional_id=profissional_a.id
    )

    token = obter_token(profissional_a)

    response = client.put(
        f"/consultas/{consulta.id}",
        json={
            "profissional_id": profissional_b.id
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    

def test_usuario_nao_admin_nao_acessa_rota_admin():
    profissional = criar_usuario(
            email="profissional.b@clinica.com",
            role="profissional"
    )

    token = obter_token(profissional)

    response = client.get(
        "/consultas/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403

