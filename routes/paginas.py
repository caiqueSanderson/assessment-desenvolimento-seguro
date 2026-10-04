from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from auth.rbac import RoleChecker
from database.database import get_session
from models.consulta import Consulta
from models.user import User


router = APIRouter()

templates = Jinja2Templates(
    directory="templates"
)


@router.get("/agenda")
def view_schedule(
    request: Request,
    current_user: User = Depends(
        RoleChecker([
            "recepcionista",
            "administrador",
        ])
    ),
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