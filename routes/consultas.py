from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from database.database import get_session
from models.consulta import Consulta
from models.schemas import (
    ConsultaCreate,
    ConsultaResponse,
    ConsultaUpdate,
)


router = APIRouter(
    prefix="/consultas",
    tags=["Consultas"],
)


@router.post(
    "/",
    response_model=ConsultaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_consulta(
    consulta: ConsultaCreate,
    session: Session = Depends(get_session),
):
    nova_consulta = Consulta.model_validate(consulta)

    session.add(nova_consulta)
    session.commit()
    session.refresh(nova_consulta)

    return nova_consulta


@router.get(
    "/",
    response_model=list[ConsultaResponse],
)
def listar_consultas(
    session: Session = Depends(get_session),
):
    statement = select(Consulta)
    return session.exec(statement).all()


@router.get(
    "/{consulta_id}",
    response_model=ConsultaResponse,
)
def buscar_consulta(
    consulta_id: int,
    session: Session = Depends(get_session),
):
    consulta = session.get(Consulta, consulta_id)

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    return consulta


@router.put(
    "/{consulta_id}",
    response_model=ConsultaResponse,
)
def atualizar_consulta(
    consulta_id: int,
    dados: ConsultaUpdate,
    session: Session = Depends(get_session),
):
    consulta = session.get(Consulta, consulta_id)

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    dados_atualizacao = dados.model_dump(exclude_unset=True)

    for campo, valor in dados_atualizacao.items():
        setattr(consulta, campo, valor)

    session.add(consulta)
    session.commit()
    session.refresh(consulta)

    return consulta


@router.delete(
    "/{consulta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_consulta(
    consulta_id: int,
    session: Session = Depends(get_session),
):
    consulta = session.get(Consulta, consulta_id)

    if consulta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada",
        )

    session.delete(consulta)
    session.commit()