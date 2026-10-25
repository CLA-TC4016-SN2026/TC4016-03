"""Modelos de casos, líneas objetivo y asignaciones. El JSON usa camelCase, como el contrato.

Los obligatorios y los límites de dominio (1 a 20 líneas, solicitud no vacía) se validan en
`src/services/casos.py`, para responder 422 y no 400 (criterio O-6).
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from src.schemas.base import Esquema
from src.schemas.usuarios import UsuarioResumen


class EstadoCaso(StrEnum):
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"


class FuncionAsignacion(StrEnum):
    MP_SOLICITANTE = "MP_SOLICITANTE"
    ANALISTA = "ANALISTA"
    PERITO = "PERITO"


class NuevaLinea(Esquema):
    msisdn: str = Field(max_length=50)


class LineaObjetivo(Esquema):
    id: UUID
    msisdn: str
    msisdn_mostrado: str


class NuevoCaso(Esquema):
    numero_solicitud: str = Field(max_length=50)
    mp_solicitante_id: UUID
    analista_id: UUID | None = None
    lineas: list[NuevaLinea]


class CambioCaso(Esquema):
    """PATCH: el único cambio admitido es cerrar el caso (O-4)."""

    estado: Literal["CERRADO"]


class CasoResumen(Esquema):
    folio: str
    numero_solicitud: str
    estado: EstadoCaso
    analista: UsuarioResumen | None = None


class Caso(CasoResumen):
    creado_en: datetime
    cerrado_en: datetime | None
    conservar_hasta: date | None
    mp_solicitante: UsuarioResumen
    peritos: list[UsuarioResumen]
    lineas: list[LineaObjetivo]


class Asignacion(Esquema):
    usuario: UsuarioResumen
    funcion: FuncionAsignacion
    desde: datetime
