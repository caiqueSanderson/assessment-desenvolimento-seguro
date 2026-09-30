from fastapi import FastAPI
from contextlib import asynccontextmanager

from database.database import create_db_and_tables
from routes.consultas import router as consultas_router
from routes.paginas import router as paginas_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title="Clínica API",
    version="1.0.0",
    description="API REST para gerenciamento de consultas médicas.",
    lifespan=lifespan
)

app.include_router(consultas_router)
app.include_router(paginas_router)


@app.get("/")
def root():
    return {
        "message": "Clínica API funcionando"
    }