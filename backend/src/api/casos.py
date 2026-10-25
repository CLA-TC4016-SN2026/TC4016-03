"""Casos, líneas objetivo y asignaciones (S05-S06-A1), protegidos por rol (S05-S06-A2).

Roles según `x-roles` de `S05_S06_A1/openapi_equipo.yaml`. ADMINISTRADOR y AUDITOR no ven
casos. Un caso no se borra ni se edita: solo se cierra (O-4), por eso no hay PUT ni DELETE.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response, status

from src.api.deps import requiere_roles
from src.db.connection import Db
from src.schemas.auth import Rol, UsuarioActual
from src.schemas.casos import (
    Asignacion,
    CambioCaso,
    Caso,
    CasoResumen,
    EstadoCaso,
    LineaObjetivo,
    NuevaLinea,
    NuevoCaso,
)
from src.schemas.usuarios import ReferenciaUsuario
from src.services import casos as servicio

router = APIRouter(prefix="/casos", tags=["casos"])

Lector = Annotated[
    UsuarioActual, Depends(requiere_roles(Rol.COORDINADOR, Rol.ANALISTA, Rol.MP_PERITO))
]
Coordinador = Annotated[UsuarioActual, Depends(requiere_roles(Rol.COORDINADOR))]


@router.get("", response_model=list[CasoResumen])
def listar_casos(
    db: Db,
    usuario: Lector,
    estado: EstadoCaso | None = None,
    sin_analista: Annotated[bool, Query(alias="sinAnalista")] = False,
) -> list[dict]:
    return servicio.listar(db, usuario, estado, sin_analista)


@router.post("", response_model=Caso, status_code=status.HTTP_201_CREATED)
def crear_caso(nuevo: NuevoCaso, db: Db, usuario: Coordinador, response: Response) -> dict:
    caso = servicio.crear(db, nuevo, usuario)
    response.headers["Location"] = f"/api/casos/{caso['folio']}"
    return caso


@router.get("/{folio}", response_model=Caso)
def obtener_caso(folio: str, db: Db, usuario: Lector) -> dict:
    return servicio.obtener(db, folio, usuario)


@router.patch("/{folio}", response_model=Caso)
def actualizar_caso(folio: str, _: CambioCaso, db: Db, usuario: Coordinador) -> dict:
    return servicio.cerrar(db, folio, usuario)


@router.get("/{folio}/lineas", response_model=list[LineaObjetivo])
def listar_lineas(folio: str, db: Db, usuario: Lector) -> list[dict]:
    return servicio.listar_lineas(db, folio, usuario)


@router.post("/{folio}/lineas", response_model=LineaObjetivo, status_code=status.HTTP_201_CREATED)
def agregar_linea(
    folio: str, nueva: NuevaLinea, db: Db, usuario: Coordinador, response: Response
) -> dict:
    linea = servicio.agregar_linea(db, folio, nueva, usuario)
    response.headers["Location"] = f"/api/casos/{folio}/lineas"
    return linea


@router.put("/{folio}/analista", response_model=Asignacion)
def asignar_analista(
    folio: str, referencia: ReferenciaUsuario, db: Db, usuario: Coordinador
) -> dict:
    return servicio.asignar_analista(db, folio, referencia.usuario_id, usuario)


@router.delete("/{folio}/analista", status_code=status.HTTP_204_NO_CONTENT)
def retirar_analista(folio: str, db: Db, usuario: Coordinador) -> None:
    servicio.retirar_analista(db, folio, usuario)


@router.post("/{folio}/peritos", response_model=Asignacion, status_code=status.HTTP_201_CREATED)
def asignar_perito(
    folio: str, referencia: ReferenciaUsuario, db: Db, usuario: Coordinador, response: Response
) -> dict:
    asignacion = servicio.asignar_perito(db, folio, referencia.usuario_id, usuario)
    response.headers["Location"] = f"/api/casos/{folio}/peritos/{referencia.usuario_id}"
    return asignacion


@router.delete("/{folio}/peritos/{usuarioId}", status_code=status.HTTP_204_NO_CONTENT)
def retirar_perito(
    folio: str,
    usuario_id: Annotated[UUID, Path(alias="usuarioId")],
    db: Db,
    usuario: Coordinador,
) -> None:
    servicio.retirar_perito(db, folio, usuario_id, usuario)
