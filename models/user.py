from typing import Optional
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    email: str = Field(
        index=True,
        unique=True,
    )

    password_hash: str
    role: str = Field(default="recepcionista")
    mfa_enabled: bool = Field(default=False)

class UserCreate(SQLModel):
    name: str
    email: str
    password: str

class UserSignIn(SQLModel):
    email: str
    password: str
    mfa_code: str | None = None