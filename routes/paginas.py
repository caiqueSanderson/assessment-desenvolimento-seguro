from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from database.database import get_session
from models.consulta import Consulta


router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/agenda")
def visualizar_agenda(
    request: Request,
    session: Session = Depends(get_session),
):
    consultas = session.exec(
        select(Consulta)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="consultas.html",
        context={
            "consultas": consultas,
        },
    )