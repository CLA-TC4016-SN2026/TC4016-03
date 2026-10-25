"""Reglas de negocio de perfiles de concesionario (RF-29, RD-07).

- Cada perfil pertenece al analista que lo creó; los demás lo ven y lo copian, pero no lo
  editan (RF-29-AC-5).
- Editar crea una versión nueva; las anteriores no cambian (RF-29-AC-4).
- Un perfil solo se guarda si es interpretable: cada tipo de evento traducido (RF-29-AC-2) y
  coordenadas o Cell ID según lo que entregue el concesionario (RF-29-AC-6).
"""

from typing import Any
from uuid import UUID

import psycopg
from fastapi import status

from src.core.errores import ErrorDominio, no_encontrado, no_procesable
from src.db import perfiles as repo
from src.schemas.auth import UsuarioActual
from src.schemas.perfiles import CopiaPerfil, DefinicionPerfil

_COLUMNAS_OBLIGATORIAS = ("msisdnObjetivo", "fecha")


def _validar(d: DefinicionPerfil) -> None:
    for campo, valor in (
        ("nombre", d.nombre),
        ("concesionario", d.concesionario),
        ("formatoFecha", d.formato_fecha),
        ("formatoHora", d.formato_hora),
    ):
        if not valor.strip():
            raise no_procesable(f"Faltan: {campo}", campo)

    if not d.traducciones:
        raise no_procesable("El perfil debe traducir al menos un tipo de evento", "traducciones")
    valores = [t.valor_concesionario.strip() for t in d.traducciones]
    if "" in valores or len(set(valores)) != len(valores):
        raise no_procesable(
            "Cada valor de tipo del concesionario debe aparecer una sola vez", "traducciones"
        )

    requeridas = list(_COLUMNAS_OBLIGATORIAS)
    if d.entrega_coordenadas:
        requeridas += ["latitud", "longitud"]
        if d.formato_coordenadas is None:
            raise no_procesable("Faltan: formatoCoordenadas", "formatoCoordenadas")
    else:
        requeridas.append("cellId")
    for campo in requeridas:
        if not d.mapeo_columnas.get(campo, "").strip():
            raise no_procesable(f"Falta la columna de: {campo}", f"mapeoColumnas.{campo}")

    if d.encabezados is not None:
        usadas = list(d.mapeo_columnas.values())
        if d.contraparte is not None:
            usadas += [c for c in (d.contraparte.saliente_y_datos, d.contraparte.entrante) if c]
        for columna in usadas:
            if columna not in d.encabezados:
                raise no_procesable(
                    f"La columna «{columna}» no está en los encabezados", "mapeoColumnas"
                )


def _a_fila(d: DefinicionPerfil) -> dict[str, Any]:
    fila = d.model_dump()
    fila["contraparte"] = d.contraparte.model_dump(by_alias=True) if d.contraparte else None
    return fila


def _definicion(perfil: dict[str, Any], v: dict[str, Any]) -> dict[str, Any]:
    return {
        "nombre": perfil["nombre"],
        "concesionario": perfil["concesionario"],
        "encabezados": v["encabezados"],
        "mapeo_columnas": v["mapeo_columnas"],
        "contraparte": v["contraparte"],
        "formato_fecha": v["formato_fecha"],
        "formato_hora": v["formato_hora"],
        "unidad_duracion": v["unidad_duracion"],
        "codificacion": v["codificacion"],
        "separador": v["separador"],
        "formato_coordenadas": v["formato_coordenadas"],
        "entrega_coordenadas": v["entrega_coordenadas"],
        "traducciones": [
            {k: t[k] for k in ("valor_concesionario", "tipo", "direccion", "resultado")}
            for t in v["traducciones"]
        ],
    }


def _version(perfil: dict[str, Any], v: dict[str, Any]) -> dict[str, Any]:
    return {
        "perfil_id": v["perfil_id"],
        "version": v["numero"],
        "creada_en": v["creada_en"],
        "creada_por": {
            "id": v["autor_id"],
            "nombre_completo": v["autor_nombre"],
            "roles": v["autor_roles"],
        },
        "definicion": _definicion(perfil, v),
    }


def _perfil(conn: psycopg.Connection, p: dict[str, Any], usuario: UsuarioActual) -> dict[str, Any]:
    vigente = repo.listar_versiones(conn, p["id"], p["version_vigente"])[0]
    return {
        "id": p["id"],
        "nombre": p["nombre"],
        "concesionario": p["concesionario"],
        "propietario": {
            "id": p["propietario_id"],
            "nombre_completo": p["propietario_nombre"],
            "roles": p["propietario_roles"],
        },
        "copiado_de": p["copiado_de"],
        "version_vigente": p["version_vigente"],
        "editable": p["propietario_id"] == usuario.id,
        "definicion": _definicion(p, vigente),
    }


def _obtener(conn: psycopg.Connection, perfil_id: UUID, bloquear: bool = False) -> dict[str, Any]:
    perfil = repo.obtener(conn, perfil_id, bloquear)
    if perfil is None:
        raise no_encontrado("Perfil no encontrado")
    return perfil


def listar(conn: psycopg.Connection, usuario: UsuarioActual) -> list[dict[str, Any]]:
    return [_perfil(conn, p, usuario) for p in repo.listar(conn)]


def obtener(conn: psycopg.Connection, perfil_id: UUID, usuario: UsuarioActual) -> dict[str, Any]:
    return _perfil(conn, _obtener(conn, perfil_id), usuario)


def crear(
    conn: psycopg.Connection, nuevo: DefinicionPerfil | CopiaPerfil, usuario: UsuarioActual
) -> dict[str, Any]:
    if isinstance(nuevo, CopiaPerfil):
        original = repo.obtener(conn, nuevo.copia_de)
        if original is None:
            raise no_procesable("copiaDe no corresponde a un perfil existente", "copiaDe")
        vigente = repo.listar_versiones(conn, original["id"], original["version_vigente"])[0]
        fila = _definicion(original, vigente)
        fila["nombre"] = f"{original['nombre'][:92]} (copia)"
        copiado_de = original["id"]
    else:
        _validar(nuevo)
        fila = _a_fila(nuevo)
        copiado_de = None

    perfil_id = repo.crear(
        conn, fila["nombre"].strip(), fila["concesionario"].strip(), usuario.id, copiado_de
    )
    repo.crear_version(conn, perfil_id, 1, usuario.id, fila)
    return obtener(conn, perfil_id, usuario)


def listar_versiones(conn: psycopg.Connection, perfil_id: UUID) -> list[dict[str, Any]]:
    perfil = _obtener(conn, perfil_id)
    return [_version(perfil, v) for v in repo.listar_versiones(conn, perfil_id)]


def obtener_version(conn: psycopg.Connection, perfil_id: UUID, numero: int) -> dict[str, Any]:
    perfil = _obtener(conn, perfil_id)
    versiones = repo.listar_versiones(conn, perfil_id, numero)
    if not versiones:
        raise no_encontrado("Versión no encontrada")
    return _version(perfil, versiones[0])


def crear_version(
    conn: psycopg.Connection, perfil_id: UUID, d: DefinicionPerfil, usuario: UsuarioActual
) -> dict[str, Any]:
    perfil = _obtener(conn, perfil_id, bloquear=True)
    if perfil["propietario_id"] != usuario.id:
        raise ErrorDominio(status.HTTP_403_FORBIDDEN, "Permiso insuficiente")
    _validar(d)
    numero = perfil["version_vigente"] + 1
    repo.renombrar(conn, perfil_id, d.nombre.strip(), d.concesionario.strip())
    repo.crear_version(conn, perfil_id, numero, usuario.id, _a_fila(d))
    return obtener_version(conn, perfil_id, numero)
