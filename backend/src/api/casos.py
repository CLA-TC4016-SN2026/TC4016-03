"""CRUD de casos (S05-S06-A1), protegido por rol (S05-S06-A2).

Roles según `x-roles` de `S05_S06_A1/openapi_equipo.yaml`. ADMINISTRADOR y AUDITOR no ven casos.
"""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg import errors

from src.api.deps import requiere_roles
from src.db import casos as repo
from src.db.connection import get_db
from src.schemas.auth import Rol
from src.schemas.casos import CambioCaso, Caso, NuevoCaso

router = APIRouter(prefix="/casos", tags=["casos"])

Db = Annotated[psycopg.Connection, Depends(get_db)]

_LECTURA = [Depends(requiere_roles(Rol.COORDINADOR, Rol.ANALISTA, Rol.MP_PERITO))]
_ESCRITURA = [Depends(requiere_roles(Rol.COORDINADOR))]

_NO_ENCONTRADO = HTTPException(status.HTTP_404_NOT_FOUND, detail="Caso no encontrado")
_USUARIO_INEXISTENTE = HTTPException(
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    detail="mpSolicitanteId o analistaId no corresponde a un usuario existente",
)


@router.get("", response_model=list[Caso], dependencies=_LECTURA)
def listar_casos(db: Db) -> list[dict]:
    return repo.listar(db)


@router.post(
    "", response_model=Caso, status_code=status.HTTP_201_CREATED, dependencies=_ESCRITURA
)
def crear_caso(nuevo: NuevoCaso, db: Db, response: Response) -> dict:
    try:
        caso = repo.crear(db, nuevo)
    except errors.ForeignKeyViolation:
        raise _USUARIO_INEXISTENTE
    response.headers["Location"] = f"/api/casos/{caso['folio']}"
    return caso


@router.get("/{folio}", response_model=Caso, dependencies=_LECTURA)
def obtener_caso(folio: str, db: Db) -> dict:
    caso = repo.obtener(db, folio)
    if caso is None:
        raise _NO_ENCONTRADO
    return caso


@router.put("/{folio}", response_model=Caso, dependencies=_ESCRITURA)
def reemplazar_caso(folio: str, cambio: CambioCaso, db: Db) -> dict:
    try:
        caso = repo.reemplazar(db, folio, cambio)
    except errors.ForeignKeyViolation:
        raise _USUARIO_INEXISTENTE
    if caso is None:
        raise _NO_ENCONTRADO
    return caso


@router.delete(
    "/{folio}", status_code=status.HTTP_204_NO_CONTENT, dependencies=_ESCRITURA
)
def borrar_caso(folio: str, db: Db) -> None:
    if not repo.borrar(db, folio):
        raise _NO_ENCONTRADO
