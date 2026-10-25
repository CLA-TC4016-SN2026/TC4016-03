"""Modelos de perfiles de concesionario (RF-29). Las reglas de dominio viven en
`src/services/perfiles.py`."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from src.schemas.base import Esquema
from src.schemas.usuarios import UsuarioResumen


class TipoEvento(StrEnum):
    VOZ = "VOZ"
    SMS = "SMS"
    DATOS = "DATOS"


class TraduccionTipo(Esquema):
    valor_concesionario: str = Field(max_length=100)
    tipo: TipoEvento
    direccion: Literal["ENTRANTE", "SALIENTE"] | None = None
    resultado: Literal["CONTESTADA", "NO_CONTESTADA"] | None = None


class Contraparte(Esquema):
    saliente_y_datos: str | None = None
    entrante: str | None = None


class DefinicionPerfil(Esquema):
    nombre: str = Field(max_length=100)
    concesionario: str = Field(max_length=100)
    encabezados: list[str] | None = None
    mapeo_columnas: dict[str, str]
    contraparte: Contraparte | None = None
    formato_fecha: str = Field(max_length=30)
    formato_hora: str = Field(max_length=30)
    unidad_duracion: Literal["SEGUNDOS", "MINUTOS"] = "SEGUNDOS"
    codificacion: Literal["UTF-8", "WINDOWS-1252", "ISO-8859-1"] = "UTF-8"
    separador: str | None = Field(default=None, max_length=1)
    formato_coordenadas: Literal["DECIMAL", "GMS"] | None = None
    entrega_coordenadas: bool
    traducciones: list[TraduccionTipo]


class CopiaPerfil(Esquema):
    copia_de: UUID


class Perfil(Esquema):
    id: UUID
    nombre: str
    concesionario: str
    propietario: UsuarioResumen
    copiado_de: UUID | None
    version_vigente: int
    editable: bool
    definicion: DefinicionPerfil


class VersionPerfil(Esquema):
    perfil_id: UUID
    version: int
    creada_en: datetime
    creada_por: UsuarioResumen
    definicion: DefinicionPerfil
