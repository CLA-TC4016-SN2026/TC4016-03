"""Consultas de casos, líneas objetivo y asignaciones.

Siempre parametrizadas: los valores nunca se concatenan al SQL. Las reglas de negocio viven en
`src/services/casos.py`; aquí solo se lee y escribe.
"""

from typing import Any
from uuid import UUID

import psycopg

_CASO = "folio, numero_solicitud, estado, creado_en, cerrado_en, conservar_hasta"
_USUARIO = "u.id, u.nombre_completo, u.roles::text[] AS roles"


def listar(
    conn: psycopg.Connection,
    usuario_id: UUID | None,
    funciones: list[str],
    estado: str | None,
    sin_analista: bool,
) -> list[dict[str, Any]]:
    """Casos con su analista vigente. `usuario_id=None` ve todos (coordinador); si no, solo
    los casos donde el usuario tiene una asignación vigente en alguna de `funciones` (RNF-02)."""
    return conn.execute(
        """
        SELECT c.folio, c.numero_solicitud, c.estado,
               u.id AS analista_id, u.nombre_completo AS analista_nombre,
               u.roles::text[] AS analista_roles
          FROM casos c
          LEFT JOIN asignaciones a
                 ON a.caso_folio = c.folio AND a.funcion = 'ANALISTA' AND a.hasta IS NULL
          LEFT JOIN usuarios u ON u.id = a.usuario_id
         WHERE (%(usuario)s::uuid IS NULL OR EXISTS (
                   SELECT 1 FROM asignaciones x
                    WHERE x.caso_folio = c.folio AND x.usuario_id = %(usuario)s
                      AND x.hasta IS NULL AND x.funcion::text = ANY (%(funciones)s)))
           AND (%(estado)s::estado_caso IS NULL OR c.estado = %(estado)s::estado_caso)
           AND (NOT %(sin_analista)s OR a.id IS NULL)
         ORDER BY c.creado_en, c.folio
        """,
        {
            "usuario": usuario_id,
            "funciones": funciones,
            "estado": estado,
            "sin_analista": sin_analista,
        },
    ).fetchall()


def obtener(conn: psycopg.Connection, folio: str, bloquear: bool = False) -> dict[str, Any] | None:
    sufijo = " FOR UPDATE" if bloquear else ""
    return conn.execute(f"SELECT {_CASO} FROM casos WHERE folio = %s{sufijo}", (folio,)).fetchone()


def tiene_asignacion(
    conn: psycopg.Connection, folio: str, usuario_id: UUID, funciones: list[str]
) -> bool:
    return (
        conn.execute(
            """
            SELECT 1 FROM asignaciones
             WHERE caso_folio = %s AND usuario_id = %s AND hasta IS NULL
               AND funcion::text = ANY (%s)
            """,
            (folio, usuario_id, funciones),
        ).fetchone()
        is not None
    )


def crear(conn: psycopg.Connection, numero_solicitud: str, creado_por: UUID) -> dict[str, Any]:
    # El folio VIN-AAAA-NNNNNN lo genera la base (R-3).
    return conn.execute(
        f"INSERT INTO casos (numero_solicitud, creado_por) VALUES (%s, %s) RETURNING {_CASO}",
        (numero_solicitud, creado_por),
    ).fetchone()


def cerrar(conn: psycopg.Connection, folio: str) -> dict[str, Any]:
    return conn.execute(
        f"""
        UPDATE casos SET estado = 'CERRADO', cerrado_en = now()
         WHERE folio = %s RETURNING {_CASO}
        """,
        (folio,),
    ).fetchone()


# ---------- Líneas objetivo ----------


def listar_lineas(conn: psycopg.Connection, folio: str) -> list[dict[str, Any]]:
    return conn.execute(
        "SELECT id, msisdn FROM lineas_objetivo WHERE caso_folio = %s ORDER BY msisdn",
        (folio,),
    ).fetchall()


def contar_lineas(conn: psycopg.Connection, folio: str) -> int:
    return conn.execute(
        "SELECT count(*) AS n FROM lineas_objetivo WHERE caso_folio = %s", (folio,)
    ).fetchone()["n"]


def existe_linea(conn: psycopg.Connection, folio: str, msisdn: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM lineas_objetivo WHERE caso_folio = %s AND msisdn = %s", (folio, msisdn)
        ).fetchone()
        is not None
    )


def agregar_linea(conn: psycopg.Connection, folio: str, msisdn: str) -> dict[str, Any]:
    return conn.execute(
        "INSERT INTO lineas_objetivo (caso_folio, msisdn) VALUES (%s, %s) RETURNING id, msisdn",
        (folio, msisdn),
    ).fetchone()


# ---------- Asignaciones ----------


def asignados(conn: psycopg.Connection, folio: str) -> list[dict[str, Any]]:
    """Asignaciones vigentes del caso, con el resumen del usuario."""
    return conn.execute(
        f"""
        SELECT a.funcion::text AS funcion, a.desde, {_USUARIO}
          FROM asignaciones a JOIN usuarios u ON u.id = a.usuario_id
         WHERE a.caso_folio = %s AND a.hasta IS NULL
         ORDER BY a.desde, u.nombre_completo
        """,
        (folio,),
    ).fetchall()


def asignacion_vigente(
    conn: psycopg.Connection, folio: str, funcion: str, usuario_id: UUID | None = None
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, usuario_id, desde FROM asignaciones
         WHERE caso_folio = %s AND funcion = %s::funcion_asignacion AND hasta IS NULL
           AND (%s::uuid IS NULL OR usuario_id = %s)
        """,
        (folio, funcion, usuario_id, usuario_id),
    ).fetchone()


def asignar(
    conn: psycopg.Connection, folio: str, usuario_id: UUID, funcion: str
) -> dict[str, Any]:
    return conn.execute(
        """
        INSERT INTO asignaciones (caso_folio, usuario_id, funcion)
        VALUES (%s, %s, %s::funcion_asignacion) RETURNING desde
        """,
        (folio, usuario_id, funcion),
    ).fetchone()


def cerrar_asignacion(conn: psycopg.Connection, asignacion_id: UUID) -> None:
    # El historial se conserva: la asignación se cierra, no se borra (RNF-03).
    conn.execute("UPDATE asignaciones SET hasta = now() WHERE id = %s", (asignacion_id,))
