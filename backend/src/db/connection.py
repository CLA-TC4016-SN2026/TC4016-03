"""Acceso a PostgreSQL.

Conexión directa con psycopg para el arranque del proyecto. Cuando existan
tablas, la sesión de SQLAlchemy vivirá en este mismo paquete.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from src.core.config import get_settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Abre una conexión y la cierra al salir del bloque `with`."""
    with psycopg.connect(str(get_settings().database_url), connect_timeout=5) as conn:
        yield conn


def get_db() -> Iterator[psycopg.Connection]:
    """Dependencia de FastAPI: una transacción por petición, con filas como diccionarios.

    Al salir hace commit; si la petición lanza una excepción, rollback.
    """
    with get_connection() as conn:
        conn.row_factory = dict_row
        yield conn
