from fastapi import APIRouter, Depends, Form, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from auth.mfa import verify_mfa_code
from auth.oauth2 import (
    authenticate_client,
    create_m2m_token,
)
from auth.rbac import RoleChecker
from database.database import get_session
from models.user import User, UserCreate, UserSignIn


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"],
)

hash_password = HashPassword()

limiter = Limiter(key_func=get_remote_address)


def authenticate_user(
    email: str,
    password: str,
    session: Session,
    mfa_code: str | None = None,
) -> User:

    user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if not user or not hash_password.verify_hash(
        password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.mfa_enabled:

        if not verify_mfa_code(mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA inválido",
            )

    return user


def generate_user_token(
    user: User,
) -> str:

    return create_access_token(
        subject=user.id,
        claims={
            "client_type": "user",
            "email": user.email,
            "role": user.role,
        },
    )


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
)
def signup(
    user_data: UserCreate,
    session: Session = Depends(get_session),
):

    existing_user = session.exec(
        select(User).where(
            User.email == user_data.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado",
        )

    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password.create_hash(
            user_data.password
        ),
        role="recepcionista",
        mfa_enabled=False,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "message": "Usuário criado com sucesso",
        "user_id": user.id,
        "role": user.role,
    }


@router.post("/signin")
def signin(
    credentials: UserSignIn,
    session: Session = Depends(get_session),
):

    user = authenticate_user(
        email=credentials.email,
        password=credentials.password,
        mfa_code=credentials.mfa_code,
        session=session,
    )

    return {
        "access_token": generate_user_token(user),
        "token_type": "bearer",
    }


@router.post("/swagger-token")
@limiter.limit("5 per minute")
def swagger_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    mfa_code: str | None = Form(default=None),
    session: Session = Depends(get_session),
):

    user = authenticate_user(
        email=form_data.username,
        password=form_data.password,
        mfa_code=mfa_code,
        session=session,
    )

    return {
        "access_token": generate_user_token(user),
        "token_type": "bearer",
    }


@router.post("/token")
def token(
    client_id: str = Form(...),
    client_secret: str = Form(...),
):

    client = authenticate_client(
        client_id,
        client_secret,
    )

    return {
        "access_token": create_m2m_token(
            client_id,
            client,
        ),
        "token_type": "bearer",
        "scope": " ".join(client["scopes"]),
    }


@router.post(
    "/professionals",
    status_code=status.HTTP_201_CREATED,
)
def create_professional(
    user_data: UserCreate,
    current_user: User = Depends(
        RoleChecker(["administrador"])
    ),
    session: Session = Depends(get_session),
):

    existing_user = session.exec(
        select(User).where(
            User.email == user_data.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado",
        )

    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password.create_hash(
            user_data.password
        ),
        role="profissional",
        mfa_enabled=False,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "message": "Profissional criado com sucesso",
        "user_id": user.id,
        "role": user.role,
    }