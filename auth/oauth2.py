from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from auth.jwt_handler import (
    create_access_token,
    verify_access_token,
)

from config import settings

CLIENTS = {
    "laboratorio_01": {
        "client_secret": settings.LAB_CLIENT_SECRET,
        "client_type": "m2m",
        "scopes": [
            "laboratorio:read",
            "consultas:read",
        ],
    }
}


m2m_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    scopes={
        "laboratorio:read":
            "Consultar recursos disponibilizados ao laboratório",
        "consultas:read":
            "Consultar consultas autorizadas",
        "consultas:write":
            "Criar ou alterar consultas",
    },
)


def authenticate_client(
    client_id: str,
    client_secret: str,
) -> dict:

    client = CLIENTS.get(client_id)

    if (
        not client
        or client["client_secret"] != client_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cliente inválido",
        )

    return client


def create_m2m_token(
    client_id: str,
    client: dict,
) -> str:

    return create_access_token(
        subject=client_id,
        claims={
            "client_id": client_id,
            "client_type": "m2m",
            "scope": " ".join(client["scopes"]),
        },
    )


def get_current_client(
    security_scopes: SecurityScopes,
    token: str = Depends(m2m_oauth2_scheme),
) -> dict:

    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("client_type") != "m2m":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de integração esperado",
        )

    token_scopes = payload.get(
        "scope",
        "",
    ).split()

    for required_scope in security_scopes.scopes:

        if required_scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Escopo insuficiente: {required_scope}",
            )

    return payload


def require_client_scope(
    required_scope: str,
):

    def dependency(
        client: dict = Security(
            get_current_client,
            scopes=[required_scope],
        ),
    ) -> dict:

        return client

    return dependency