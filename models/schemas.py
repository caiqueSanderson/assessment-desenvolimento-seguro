from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsultaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: int
    profissional_id: int
    data_hora: datetime
    status: str = "agendada"


class ConsultaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: int | None = None
    profissional_id: int | None = None
    data_hora: datetime | None = None
    status: str | None = None


class ConsultaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    profissional_id: int
    data_hora: datetime
    status: str