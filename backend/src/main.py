"""Punto de entrada de la API de VÍNCULO.

Desarrollo (desde vinculo/backend/):
    uv run uvicorn src.main:app --reload
"""

from fastapi import FastAPI

from src.api import auth, casos, health, perfiles, usuarios
from src.core.config import get_settings
from src.core.errores import registrar_manejadores

# Falla al arrancar, no en la primera petición, si falta JWT_SECRET o JWT_EXPIRATION.
get_settings()

app = FastAPI(
    title="VÍNCULO API",
    version="0.3.0",
    summary="Análisis de sábanas telefónicas (CDR): metadatos, nunca contenido.",
)

# Todos los errores salen como application/problem+json (RFC 9457).
registrar_manejadores(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(casos.router)
app.include_router(perfiles.router)
