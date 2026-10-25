"""Perfiles de concesionario (RF-29). Solo el analista los gestiona (`x-roles`)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from src.api.deps import requiere_roles
from src.db.connection import Db
from src.schemas.auth import Rol, UsuarioActual
from src.schemas.perfiles import CopiaPerfil, DefinicionPerfil, Perfil, VersionPerfil
from src.services import perfiles as servicio

router = APIRouter(prefix="/perfiles", tags=["perfiles"])

Analista = Annotated[UsuarioActual, Depends(requiere_roles(Rol.ANALISTA))]
PerfilId = Annotated[UUID, Path(alias="perfilId")]


def _nuevo_perfil(cuerpo: Annotated[dict[str, Any], Body()]) -> DefinicionPerfil | CopiaPerfil:
    # NuevoPerfil es oneOf: `copiaDe` decide la rama, así los errores son los de una sola.
    modelo = CopiaPerfil if "copiaDe" in cuerpo else DefinicionPerfil
    try:
        return modelo.model_validate(cuerpo)
    except ValidationError as e:
        raise RequestValidationError([{**err, "loc": ("body", *err["loc"])} for err in e.errors()])


@router.get("", response_model=list[Perfil])
def listar_perfiles(db: Db, usuario: Analista) -> list[dict]:
    return servicio.listar(db, usuario)


@router.post("", response_model=Perfil, status_code=status.HTTP_201_CREATED)
def crear_perfil(
    nuevo: Annotated[DefinicionPerfil | CopiaPerfil, Depends(_nuevo_perfil)],
    db: Db,
    usuario: Analista,
    response: Response,
) -> dict:
    perfil = servicio.crear(db, nuevo, usuario)
    response.headers["Location"] = f"/api/perfiles/{perfil['id']}"
    return perfil


@router.get("/{perfilId}", response_model=Perfil)
def obtener_perfil(perfil_id: PerfilId, db: Db, usuario: Analista) -> dict:
    return servicio.obtener(db, perfil_id, usuario)


@router.get("/{perfilId}/versiones", response_model=list[VersionPerfil])
def listar_versiones(perfil_id: PerfilId, db: Db, _: Analista) -> list[dict]:
    return servicio.listar_versiones(db, perfil_id)


@router.post(
    "/{perfilId}/versiones", response_model=VersionPerfil, status_code=status.HTTP_201_CREATED
)
def crear_version(
    perfil_id: PerfilId, definicion: DefinicionPerfil, db: Db, usuario: Analista, response: Response
) -> dict:
    version = servicio.crear_version(db, perfil_id, definicion, usuario)
    response.headers["Location"] = f"/api/perfiles/{perfil_id}/versiones/{version['version']}"
    return version


@router.get("/{perfilId}/versiones/{version}", response_model=VersionPerfil)
def obtener_version(
    perfil_id: PerfilId, version: Annotated[int, Path(ge=1)], db: Db, _: Analista
) -> dict:
    return servicio.obtener_version(db, perfil_id, version)
