"""Punto de entrada de la API de VÍNCULO.

Desarrollo (desde vinculo/backend/):
    uv run uvicorn src.main:app --reload
"""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api import auth, casos, health
from src.core.config import get_settings

# Falla al arrancar, no en la primera petición, si falta JWT_SECRET o JWT_EXPIRATION.
get_settings()

app = FastAPI(
    title="VÍNCULO API",
    version="0.2.0",
    summary="Análisis de sábanas telefónicas (CDR): metadatos, nunca contenido.",
)


@app.exception_handler(RequestValidationError)
async def errores_de_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI repite en "input" el valor rechazado; con una contraseña la devolvería en claro.
    errores = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errores)},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(casos.router)
