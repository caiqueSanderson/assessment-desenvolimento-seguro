import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from auth.authenticate import get_current_user
from auth.oauth2 import require_client_scope
from auth.rbac import RoleChecker
from database.database import get_session
from models.consulta import Consulta
from models.schemas import (
    CreateAppointment,
    ConsultaResponse,
    ConsultaUpdate,
)
from models.user import User


router = APIRouter(
    prefix="/consultas",
    tags=["Consultas"],
)


def validate_query_permission(
    current_user: User,
    consulta: Consulta,
) -> None:

    if current_user.role == "profissional":

        if consulta.profissional_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Profissional só pode gerenciar "
                    "suas próprias consultas"
                ),
            )

        return

    if current_user.role in {
        "recepcionista",
        "administrador",
    }:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Usuário sem permissão",
    )


@router.get("/admin-only")
def admin_only(
    current_user: User = Depends(
        RoleChecker(["administrador"])
    ),
):
    return {
        "message": "Área administrativa",
    }


@router.post(
    "/",
    response_model=ConsultaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    consulta: CreateAppointment,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):

    if current_user.role == "profissional":

        if consulta.profissional_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Profissional só pode criar "
                    "consultas para si mesmo"
                ),
            )

    elif current_user.role not in {
        "recepcionista",
        "administrador",
    }:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão",
        )

    appointment = Consulta(
        paciente_id=consulta.paciente_id,
        profissional_id=consulta.profissional_id,
        data_hora=consulta.data_hora,
        status=consulta.status,
        audit_token=secrets.token_urlsafe(16),
    )

    session.add(appointment)
    session.commit()
    session.refresh(appointment)

    return appointment


@router.get(
    "/",
    response_model=list[ConsultaResponse],
)
def list_appointments(
    current_user: User = Depends(RoleChecker(["profissional", "recepcionista", "administrador"])),
    session: Session = Depends(get_session),
):

    if current_user.role == "profissional":

        statement = select(Consulta).where(
            Consulta.profissional_id == current_user.id
        )

    elif current_user.role in {
        "recepcionista",
        "administrador",
    }:

        statement = select(Consulta)

    else:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão",
        )

    return session.exec(statement).all()


@router.get(
    "/integracao/consultas",
    response_model=list[ConsultaResponse],
)
def list_appointments_lab(
    client=Depends(
        require_client_scope("consultas:read")
    ),
    session: Session = Depends(get_session),
):

    return session.exec(
        select(Consulta)
    ).all()


@router.get(
    "/{consulta_id}",
    response_model=ConsultaResponse,
)
def search_appointment(
    consulta_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):

    consulta = session.get(
        Consulta,
        consulta_id,
    )

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    validate_query_permission(
        current_user,
        consulta,
    )

    return consulta


@router.put(
    "/{consulta_id}",
    response_model=ConsultaResponse,
)
def update_appointment(
    consulta_id: int,
    dados: ConsultaUpdate,
    current_user: User = Depends(RoleChecker(["administrador", "profissional"])),
    session: Session = Depends(get_session),
):

    consulta = session.get(
        Consulta,
        consulta_id,
    )

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    validate_query_permission(
        current_user,
        consulta,
    )

    dados_atualizacao = dados.model_dump(
        exclude_unset=True
    )

    if (
        current_user.role == "profissional"
        and "profissional_id" in dados_atualizacao
        and dados_atualizacao["profissional_id"]
        != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Profissional não pode transferir "
                "a consulta para outro profissional"
            ),
        )

    for campo, valor in dados_atualizacao.items():

        if valor is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"O campo '{campo}' não pode ser nulo",
            )

        setattr(
            consulta,
            campo,
            valor,
        )

    session.add(consulta)
    session.commit()
    session.refresh(consulta)

    return consulta


@router.delete(
    "/{consulta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_appointment(
    consulta_id: int,
    current_user: User = Depends(RoleChecker(["administrador"])),
    session: Session = Depends(get_session),
):

    consulta = session.get(
        Consulta,
        consulta_id,
    )

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    validate_query_permission(
        current_user,
        consulta,
    )

    session.delete(consulta)
    session.commit()