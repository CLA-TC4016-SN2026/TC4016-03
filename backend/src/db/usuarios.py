"""Consultas de usuarios. El hash solo sale de aquí hacia la verificación de contraseña."""

from typing import Any
from uuid import UUID

import psycopg

# Columnas públicas: sin contrasena_hash.
_COLUMNAS = "id, correo, nombre_completo, roles::text[] AS roles, activo, creado_en"
_RESUMEN = "id, nombre_completo, roles::text[] AS roles"


def listar_activos(conn: psycopg.Connection, rol: str | None) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        SELECT {_RESUMEN} FROM usuarios
         WHERE activo AND (%(rol)s::rol IS NULL OR %(rol)s::rol = ANY (roles))
         ORDER BY nombre_completo, id
        """,
        {"rol": rol},
    ).fetchall()


def obtener_activo(conn: psycopg.Connection, usuario_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        f"SELECT {_RESUMEN} FROM usuarios WHERE id = %s AND activo", (usuario_id,)
    ).fetchone()


def crear(
    conn: psycopg.Connection,
    correo: str,
    nombre_completo: str,
    contrasena_hash: str,
    roles: list[str],
) -> dict[str, Any]:
    return conn.execute(
        f"""
        INSERT INTO usuarios (correo, nombre_completo, contrasena_hash, roles)
        VALUES (%s, %s, %s, %s::rol[])
        RETURNING {_COLUMNAS}
        """,
        (correo, nombre_completo, contrasena_hash, roles),
    ).fetchone()


def obtener(conn: psycopg.Connection, usuario_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        f"SELECT {_COLUMNAS} FROM usuarios WHERE id = %s", (usuario_id,)
    ).fetchone()


def obtener_para_login(conn: psycopg.Connection, correo: str) -> dict[str, Any] | None:
    """Incluye el hash. Solo para el inicio de sesión."""
    return conn.execute(
        f"SELECT {_COLUMNAS}, contrasena_hash FROM usuarios WHERE lower(correo) = lower(%s)",
        (correo,),
    ).fetchone()
