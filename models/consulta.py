from datetime import datetime

from sqlmodel import Field, SQLModel


class Consulta(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    paciente_id: int
    profissional_id: int

    data_hora: datetime

    status: str = Field(default="agendada")