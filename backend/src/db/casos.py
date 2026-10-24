"""Consultas de casos. Siempre parametrizadas: los valores nunca se concatenan al SQL."""

from typing import Any

import psycopg

from src.schemas.casos import CambioCaso, NuevoCaso

_COLUMNAS = (
    "folio, numero_solicitud, estado, mp_solicitante_id, analista_id, creado_en, cerrado_en"
)


def listar(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(f"SELECT {_COLUMNAS} FROM casos ORDER BY creado_en, folio").fetchall()


def obtener(conn: psycopg.Connection, folio: str) -> dict[str, Any] | None:
    return conn.execute(
        f"SELECT {_COLUMNAS} FROM casos WHERE folio = %s", (folio,)
    ).fetchone()


def crear(conn: psycopg.Connection, caso: NuevoCaso) -> dict[str, Any]:
    return conn.execute(
        f"""
        INSERT INTO casos (numero_solicitud, mp_solicitante_id, analista_id)
        VALUES (%s, %s, %s)
        RETURNING {_COLUMNAS}
        """,
        (caso.numero_solicitud, caso.mp_solicitante_id, caso.analista_id),
    ).fetchone()


def reemplazar(conn: psycopg.Connection, folio: str, cambio: CambioCaso) -> dict[str, Any] | None:
    # cerrado_en se conserva si el caso ya estaba cerrado y se borra si se reabre.
    return conn.execute(
        f"""
        UPDATE casos
           SET numero_solicitud  = %s,
               mp_solicitante_id = %s,
               analista_id       = %s,
               estado            = %s,
               cerrado_en        = CASE
                                     WHEN %s = 'CERRADO' THEN coalesce(cerrado_en, now())
                                   END
         WHERE folio = %s
        RETURNING {_COLUMNAS}
        """,
        (
            cambio.numero_solicitud,
            cambio.mp_solicitante_id,
            cambio.analista_id,
            cambio.estado,
            cambio.estado,
            folio,
        ),
    ).fetchone()


def borrar(conn: psycopg.Connection, folio: str) -> bool:
    return conn.execute("DELETE FROM casos WHERE folio = %s", (folio,)).rowcount == 1
