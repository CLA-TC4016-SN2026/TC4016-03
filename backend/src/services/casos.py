"""Reglas de negocio de casos, líneas objetivo y asignaciones (RF-02, RF-23, RF-27, RNF-02).

- Visibilidad (RNF-02): el coordinador ve todos los casos; el analista, los que tiene
  asignados como analista; el MP/perito, los que tiene como MP solicitante o perito. Un caso
  ajeno y un folio inexistente reciben la misma respuesta 404 (RF-02-AC-9).
- Un caso no se borra ni se reabre: solo se cierra, y cerrado es de solo lectura (O-4).
- Las escrituras sobre un caso bloquean su fila (`FOR UPDATE`): dos cambios simultáneos no
  violan el límite de 20 líneas ni dejan dos analistas vigentes.
"""

from typing import Any
from uuid import UUID

import psycopg

from src.core import telefonos
from src.core.errores import conflicto, no_encontrado, no_procesable
from src.db import casos as repo
from src.db import usuarios as repo_usuarios
from src.schemas.auth import Rol, UsuarioActual
from src.schemas.casos import NuevaLinea, NuevoCaso

MAXIMO_LINEAS = 20

_FUNCIONES_POR_ROL = {
    Rol.ANALISTA: ["ANALISTA"],
    Rol.MP_PERITO: ["MP_SOLICITANTE", "PERITO"],
}


def _funciones_visibles(usuario: UsuarioActual) -> list[str] | None:
    """None = ve todos los casos. Lista vacía = no ve ninguno."""
    if usuario.rol_activo == Rol.COORDINADOR:
        return None
    return _FUNCIONES_POR_ROL.get(usuario.rol_activo, [])


def _caso_visible(
    conn: psycopg.Connection, folio: str, usuario: UsuarioActual, bloquear: bool = False
) -> dict[str, Any]:
    caso = repo.obtener(conn, folio, bloquear)
    funciones = _funciones_visibles(usuario)
    if caso is None or (
        funciones is not None and not repo.tiene_asignacion(conn, folio, usuario.id, funciones)
    ):
        raise no_encontrado("Caso no encontrado")
    return caso


def _usuario_con_rol(
    conn: psycopg.Connection, usuario_id: UUID, rol: Rol, campo: str, descripcion: str
) -> dict[str, Any]:
    usuario = repo_usuarios.obtener_activo(conn, usuario_id)
    if usuario is None or rol not in usuario["roles"]:
        raise no_procesable(f"{campo} no corresponde a un {descripcion} activo", campo)
    return usuario


def _normalizar(texto: str, campo: str) -> str:
    e164 = telefonos.normalizar(texto)
    if e164 is None:
        raise no_procesable(f"«{texto}» no es un número telefónico válido", campo)
    return e164


def _linea(fila: dict[str, Any]) -> dict[str, Any]:
    return {**fila, "msisdn_mostrado": telefonos.mostrado(fila["msisdn"])}


def _resumen(fila: dict[str, Any]) -> dict[str, Any]:
    return {"id": fila["id"], "nombre_completo": fila["nombre_completo"], "roles": fila["roles"]}


def _detalle(conn: psycopg.Connection, caso: dict[str, Any]) -> dict[str, Any]:
    asignados = repo.asignados(conn, caso["folio"])

    def por_funcion(funcion: str) -> list[dict[str, Any]]:
        return [_resumen(a) for a in asignados if a["funcion"] == funcion]

    analistas, mps = por_funcion("ANALISTA"), por_funcion("MP_SOLICITANTE")
    return {
        **caso,
        "analista": analistas[0] if analistas else None,
        "mp_solicitante": mps[0] if mps else None,
        "peritos": por_funcion("PERITO"),
        "lineas": [_linea(f) for f in repo.listar_lineas(conn, caso["folio"])],
    }


# ---------- Casos ----------


def listar(
    conn: psycopg.Connection,
    usuario: UsuarioActual,
    estado: str | None,
    sin_analista: bool,
) -> list[dict[str, Any]]:
    funciones = _funciones_visibles(usuario)
    filas = repo.listar(
        conn,
        usuario_id=None if funciones is None else usuario.id,
        funciones=funciones or [],
        estado=estado,
        sin_analista=sin_analista,
    )
    return [
        {
            "folio": f["folio"],
            "numero_solicitud": f["numero_solicitud"],
            "estado": f["estado"],
            "analista": None
            if f["analista_id"] is None
            else {
                "id": f["analista_id"],
                "nombre_completo": f["analista_nombre"],
                "roles": f["analista_roles"],
            },
        }
        for f in filas
    ]


def crear(conn: psycopg.Connection, nuevo: NuevoCaso, usuario: UsuarioActual) -> dict[str, Any]:
    numero = nuevo.numero_solicitud.strip()
    if not numero:
        raise no_procesable("Faltan: número de solicitud", "numeroSolicitud")
    if not nuevo.lineas:
        raise no_procesable("Faltan: líneas objetivo", "lineas")
    if len(nuevo.lineas) > MAXIMO_LINEAS:
        raise no_procesable(f"Un caso admite como máximo {MAXIMO_LINEAS} líneas objetivo", "lineas")

    lineas: list[str] = []
    for i, linea in enumerate(nuevo.lineas):
        e164 = _normalizar(linea.msisdn, f"lineas.{i}.msisdn")
        if e164 in lineas:
            raise no_procesable(f"La línea {telefonos.mostrado(e164)} está repetida", "lineas")
        lineas.append(e164)

    _usuario_con_rol(conn, nuevo.mp_solicitante_id, Rol.MP_PERITO, "mpSolicitanteId", "MP")
    if nuevo.analista_id is not None:
        _usuario_con_rol(conn, nuevo.analista_id, Rol.ANALISTA, "analistaId", "analista")

    caso = repo.crear(conn, numero, creado_por=usuario.id)
    repo.asignar(conn, caso["folio"], nuevo.mp_solicitante_id, "MP_SOLICITANTE")
    if nuevo.analista_id is not None:
        repo.asignar(conn, caso["folio"], nuevo.analista_id, "ANALISTA")
    for e164 in lineas:
        repo.agregar_linea(conn, caso["folio"], e164)
    return _detalle(conn, caso)


def obtener(conn: psycopg.Connection, folio: str, usuario: UsuarioActual) -> dict[str, Any]:
    return _detalle(conn, _caso_visible(conn, folio, usuario))


def cerrar(conn: psycopg.Connection, folio: str, usuario: UsuarioActual) -> dict[str, Any]:
    caso = _caso_visible(conn, folio, usuario, bloquear=True)
    if caso["estado"] == "CERRADO":
        raise conflicto("El caso ya está cerrado")
    return _detalle(conn, repo.cerrar(conn, folio))


# ---------- Líneas objetivo ----------


def listar_lineas(conn: psycopg.Connection, folio: str, usuario: UsuarioActual) -> list[dict]:
    _caso_visible(conn, folio, usuario)
    return [_linea(f) for f in repo.listar_lineas(conn, folio)]


def agregar_linea(
    conn: psycopg.Connection, folio: str, nueva: NuevaLinea, usuario: UsuarioActual
) -> dict[str, Any]:
    caso = _caso_visible(conn, folio, usuario, bloquear=True)
    if caso["estado"] == "CERRADO":
        raise conflicto("El caso está cerrado y es de solo lectura")
    e164 = _normalizar(nueva.msisdn, "msisdn")
    if repo.existe_linea(conn, folio, e164):
        raise conflicto(f"La línea {telefonos.mostrado(e164)} ya está registrada en el caso")
    if repo.contar_lineas(conn, folio) >= MAXIMO_LINEAS:
        raise no_procesable(f"El caso ya tiene el máximo de {MAXIMO_LINEAS} líneas objetivo")
    return _linea(repo.agregar_linea(conn, folio, e164))


# ---------- Asignaciones ----------


def _asignacion(usuario: dict[str, Any], funcion: str, desde: Any) -> dict[str, Any]:
    return {"usuario": _resumen(usuario), "funcion": funcion, "desde": desde}


def asignar_analista(
    conn: psycopg.Connection, folio: str, analista_id: UUID, usuario: UsuarioActual
) -> dict[str, Any]:
    _caso_visible(conn, folio, usuario, bloquear=True)
    analista = _usuario_con_rol(conn, analista_id, Rol.ANALISTA, "usuarioId", "analista")
    vigente = repo.asignacion_vigente(conn, folio, "ANALISTA")
    if vigente is not None and vigente["usuario_id"] == analista_id:
        return _asignacion(analista, "ANALISTA", vigente["desde"])
    # Reasignar cierra la vigente: el analista anterior pierde el acceso (RF-02-AC-5).
    if vigente is not None:
        repo.cerrar_asignacion(conn, vigente["id"])
    nueva = repo.asignar(conn, folio, analista_id, "ANALISTA")
    return _asignacion(analista, "ANALISTA", nueva["desde"])


def retirar_analista(conn: psycopg.Connection, folio: str, usuario: UsuarioActual) -> None:
    _caso_visible(conn, folio, usuario, bloquear=True)
    vigente = repo.asignacion_vigente(conn, folio, "ANALISTA")
    if vigente is None:
        raise no_encontrado("El caso no tiene analista asignado")
    repo.cerrar_asignacion(conn, vigente["id"])


def asignar_perito(
    conn: psycopg.Connection, folio: str, perito_id: UUID, usuario: UsuarioActual
) -> dict[str, Any]:
    _caso_visible(conn, folio, usuario, bloquear=True)
    perito = _usuario_con_rol(conn, perito_id, Rol.MP_PERITO, "usuarioId", "MP/perito")
    if repo.asignacion_vigente(conn, folio, "PERITO", perito_id) is not None:
        raise no_procesable("El usuario ya es perito del caso", "usuarioId")
    nueva = repo.asignar(conn, folio, perito_id, "PERITO")
    return _asignacion(perito, "PERITO", nueva["desde"])


def retirar_perito(
    conn: psycopg.Connection, folio: str, perito_id: UUID, usuario: UsuarioActual
) -> None:
    _caso_visible(conn, folio, usuario, bloquear=True)
    vigente = repo.asignacion_vigente(conn, folio, "PERITO", perito_id)
    if vigente is None:
        raise no_encontrado("El usuario no es perito del caso")
    repo.cerrar_asignacion(conn, vigente["id"])
