"""Consultas de perfiles de concesionario y sus versiones (RF-29). Siempre parametrizadas."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

_PERFIL = """
    p.id, p.nombre, p.concesionario, p.copiado_de, p.propietario_id,
    u.nombre_completo AS propietario_nombre, u.roles::text[] AS propietario_roles,
    (SELECT max(numero) FROM versiones_perfil v WHERE v.perfil_id = p.id) AS version_vigente
"""
_VERSION = """
    v.id, v.perfil_id, v.numero, v.creada_en, v.encabezados, v.mapeo_columnas, v.contraparte,
    v.codificacion, v.separador, v.formato_fecha, v.formato_hora, v.unidad_duracion,
    v.formato_coordenadas, v.entrega_coordenadas,
    u.id AS autor_id, u.nombre_completo AS autor_nombre, u.roles::text[] AS autor_roles
"""


def listar(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(
        f"""
        SELECT {_PERFIL} FROM perfiles_concesionario p JOIN usuarios u ON u.id = p.propietario_id
         ORDER BY p.nombre, p.id
        """
    ).fetchall()


def obtener(conn: psycopg.Connection, perfil_id: UUID, bloquear: bool = False) -> dict[str, Any] | None:
    # FOR UPDATE OF p: dos ediciones simultáneas no obtienen el mismo número de versión.
    sufijo = " FOR UPDATE OF p" if bloquear else ""
    return conn.execute(
        f"""
        SELECT {_PERFIL} FROM perfiles_concesionario p JOIN usuarios u ON u.id = p.propietario_id
         WHERE p.id = %s{sufijo}
        """,
        (perfil_id,),
    ).fetchone()


def crear(
    conn: psycopg.Connection,
    nombre: str,
    concesionario: str,
    propietario_id: UUID,
    copiado_de: UUID | None,
) -> UUID:
    return conn.execute(
        """
        INSERT INTO perfiles_concesionario (nombre, concesionario, propietario_id, copiado_de)
        VALUES (%s, %s, %s, %s) RETURNING id
        """,
        (nombre, concesionario, propietario_id, copiado_de),
    ).fetchone()["id"]


def renombrar(conn: psycopg.Connection, perfil_id: UUID, nombre: str, concesionario: str) -> None:
    conn.execute(
        "UPDATE perfiles_concesionario SET nombre = %s, concesionario = %s WHERE id = %s",
        (nombre, concesionario, perfil_id),
    )


def crear_version(
    conn: psycopg.Connection,
    perfil_id: UUID,
    numero: int,
    creada_por: UUID,
    d: dict[str, Any],
) -> None:
    """`d` es la definición en snake_case (`DefinicionPerfil.model_dump()`)."""
    version_id = conn.execute(
        """
        INSERT INTO versiones_perfil (
            perfil_id, numero, creada_por, encabezados, mapeo_columnas, contraparte,
            codificacion, separador, formato_fecha, formato_hora, unidad_duracion,
            formato_coordenadas, entrega_coordenadas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            perfil_id,
            numero,
            creada_por,
            d["encabezados"],
            Jsonb(d["mapeo_columnas"]),
            Jsonb(d["contraparte"]) if d["contraparte"] is not None else None,
            d["codificacion"],
            d["separador"],
            d["formato_fecha"],
            d["formato_hora"],
            d["unidad_duracion"],
            d["formato_coordenadas"],
            d["entrega_coordenadas"],
        ),
    ).fetchone()["id"]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO traducciones_tipo
                (version_perfil_id, valor_concesionario, tipo, direccion, resultado)
            VALUES (%s, %s, %s::tipo_evento, %s::direccion, %s::resultado)
            """,
            [
                (version_id, t["valor_concesionario"], t["tipo"], t["direccion"], t["resultado"])
                for t in d["traducciones"]
            ],
        )


def listar_versiones(
    conn: psycopg.Connection, perfil_id: UUID, numero: int | None = None
) -> list[dict[str, Any]]:
    """Versiones con sus traducciones; `numero` limita a una sola."""
    versiones = conn.execute(
        f"""
        SELECT {_VERSION} FROM versiones_perfil v JOIN usuarios u ON u.id = v.creada_por
         WHERE v.perfil_id = %s AND (%s::integer IS NULL OR v.numero = %s)
         ORDER BY v.numero
        """,
        (perfil_id, numero, numero),
    ).fetchall()
    if not versiones:
        return []
    traducciones = conn.execute(
        """
        SELECT version_perfil_id, valor_concesionario, tipo::text AS tipo,
               direccion::text AS direccion, resultado::text AS resultado
          FROM traducciones_tipo WHERE version_perfil_id = ANY (%s)
         ORDER BY valor_concesionario
        """,
        ([v["id"] for v in versiones],),
    ).fetchall()
    for v in versiones:
        v["traducciones"] = [t for t in traducciones if t["version_perfil_id"] == v["id"]]
    return versiones
