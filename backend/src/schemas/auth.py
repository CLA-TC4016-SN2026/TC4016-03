"""Modelos de autenticación. Ningún modelo de salida tiene campo de contraseña ni de hash."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from src.schemas.base import Esquema


class Rol(StrEnum):
    ADMINISTRADOR = "ADMINISTRADOR"
    COORDINADOR = "COORDINADOR"
    ANALISTA = "ANALISTA"
    MP_PERITO = "MP_PERITO"
    AUDITOR = "AUDITOR"


class NuevoUsuario(Esquema):
    correo: EmailStr
    nombre_completo: str = Field(min_length=1, max_length=200)
    contrasena: str = Field(min_length=12)
    roles: list[Rol] = Field(min_length=1)

    @field_validator("contrasena")
    @classmethod
    def _cabe_en_bcrypt(cls, valor: str) -> str:
        # bcrypt solo procesa 72 bytes; en UTF-8 una «ñ» ocupa 2.
        if len(valor.encode()) > 72:
            raise ValueError("la contraseña no puede exceder 72 bytes en UTF-8")
        return valor

    @field_validator("roles")
    @classmethod
    def _sin_repetidos(cls, valor: list[Rol]) -> list[Rol]:
        if len(set(valor)) != len(valor):
            raise ValueError("los roles no pueden repetirse")
        return valor


class Usuario(Esquema):
    id: UUID
    correo: EmailStr
    nombre_completo: str
    roles: list[Rol]
    activo: bool
    creado_en: datetime


class UsuarioActual(Usuario):
    rol_activo: Rol


class Credenciales(Esquema):
    correo: EmailStr
    contrasena: str = Field(min_length=1)
    rol: Rol | None = None


class Token(Esquema):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expira_en: int
    rol_activo: Rol
