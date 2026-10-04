from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from auth.authenticate import authenticate
from database.database import get_session
from models.user import User


class RoleChecker:
    def __init__(self, allowed_roles: list[str] | str):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        payload: dict = Depends(authenticate),
        session: Session = Depends(get_session),
    ) -> User:

        try:
            user_id = int(payload["sub"])

        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )

        user = session.exec(
            select(User).where(User.id == user_id)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
            )

        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário sem permissão para esta operação",
            )

        return user


def require_scope(required_scope: str):

    def checker(token_data: dict):
        scopes = token_data.get("scope", "").split()

        if required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Escopo insuficiente",
            )

        return token_data

    return checker