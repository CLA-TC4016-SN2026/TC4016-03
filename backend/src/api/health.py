"""Endpoint de salud: confirma que la API está viva y que llega a la base."""

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.connection import get_connection

router = APIRouter(tags=["salud"])


class Health(BaseModel):
    status: str
    postgresql: str
    postgis: str
    timezone: str


@router.get("/health", response_model=Health)
def health() -> Health:
    try:
        with get_connection() as conn:
            postgresql, postgis, timezone = conn.execute(
                "SELECT current_setting('server_version'),"
                " postgis_lib_version(),"
                " current_setting('TimeZone')"
            ).fetchone()
    except psycopg.OperationalError:
        # No se devuelve el detalle del error: podría incluir host, usuario o puerto.
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    return Health(status="ok", postgresql=postgresql, postgis=postgis, timezone=timezone)
