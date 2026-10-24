"""Modelos de entrada y salida de casos. El JSON usa camelCase, como el contrato S04."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from src.schemas.base import Esquema


class EstadoCaso(StrEnum):
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"


class NuevoCaso(Esquema):
    numero_solicitud: str = Field(min_length=1, max_length=100)
    mp_solicitante_id: UUID
    analista_id: UUID | None = None


class CambioCaso(Esquema):
    """PUT: reemplaza todos los campos editables. El folio y las fechas no se editan."""

    numero_solicitud: str = Field(min_length=1, max_length=100)
    mp_solicitante_id: UUID
    analista_id: UUID | None
    estado: EstadoCaso


class Caso(Esquema):
    folio: str
    numero_solicitud: str
    estado: EstadoCaso
    mp_solicitante_id: UUID
    analista_id: UUID | None
    creado_en: datetime
    cerrado_en: datetime | None
