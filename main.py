from fastapi import FastAPI

from database.database import create_db_and_tables
from routes.consultas import router as consultas_router


app = FastAPI(
    title="Clínica API",
    version="1.0.0",
    description="API REST para gerenciamento de consultas médicas.",
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


app.include_router(consultas_router)


@app.get("/")
def root():
    return {
        "message": "Clínica API funcionando"
    }