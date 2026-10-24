"""Middleware de autenticación y autorización, como dependencias de FastAPI.

- `usuario_actual`: exige `Authorization: Bearer <token>` válido → si no, 401.
- `requiere_roles(...)`: además exige que el rol activo del token esté permitido → si no, 403.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.seguridad import TokenInvalido, decodificar_token
from src.db import usuarios as repo_usuarios
from src.db.connection import get_db
from src.schemas.auth import Rol, UsuarioActual

# auto_error=False: la respuesta 401 la arma `usuario_actual`, con un mensaje único.
_bearer = HTTPBearer(auto_error=False, description="JWT obtenido en POST /auth/login")

_NO_AUTENTICADO = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)
_PERMISO_INSUFICIENTE = HTTPException(status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")


def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
) -> UsuarioActual:
    # Sin token, token mal formado, firma inválida o expirado: misma respuesta.
    if credenciales is None:
        raise _NO_AUTENTICADO
    try:
        claims = decodificar_token(credenciales.credentials)
        usuario_id = UUID(claims["sub"])
        rol = Rol(claims["rol"])
    except (TokenInvalido, ValueError):
        raise _NO_AUTENTICADO

    # Un token firmado no basta: la cuenta debe seguir activa y conservar el rol.
    usuario = repo_usuarios.obtener(db, usuario_id)
    if usuario is None or not usuario["activo"] or rol not in usuario["roles"]:
        raise _NO_AUTENTICADO
    return UsuarioActual(**usuario, rol_activo=rol)


UsuarioAutenticado = Annotated[UsuarioActual, Depends(usuario_actual)]


def requiere_roles(*permitidos: Rol) -> Callable[[UsuarioActual], UsuarioActual]:
    def verificar(usuario: UsuarioAutenticado) -> UsuarioActual:
        if usuario.rol_activo not in permitidos:
            raise _PERMISO_INSUFICIENTE
        return usuario

    return verificar
