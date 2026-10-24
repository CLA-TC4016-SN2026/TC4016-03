"""Autenticación: registro (solo administrador), inicio de sesión y usuario actual."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg import errors

from src.api.deps import UsuarioAutenticado, requiere_roles
from src.core.seguridad import crear_token, hashear_contrasena, verificar_contrasena
from src.db import usuarios as repo
from src.db.connection import get_db
from src.schemas.auth import Credenciales, NuevoUsuario, Rol, Token, Usuario, UsuarioActual

router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[psycopg.Connection, Depends(get_db)]

_CREDENCIALES_INCORRECTAS = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales incorrectas",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post(
    "/register",
    response_model=Usuario,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere_roles(Rol.ADMINISTRADOR))],
)
def registrar(nuevo: NuevoUsuario, db: Db, response: Response) -> dict:
    try:
        usuario = repo.crear(
            db,
            correo=nuevo.correo,
            nombre_completo=nuevo.nombre_completo,
            contrasena_hash=hashear_contrasena(nuevo.contrasena),
            roles=[rol.value for rol in nuevo.roles],
        )
    except errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya existe una cuenta con ese correo")
    response.headers["Location"] = f"/api/usuarios/{usuario['id']}"
    return usuario


@router.post("/login", response_model=Token)
def iniciar_sesion(credenciales: Credenciales, db: Db) -> Token:
    usuario = repo.obtener_para_login(db, credenciales.correo)
    # Se verifica la contraseña aunque el correo no exista, para no revelarlo por el tiempo.
    contrasena_ok = verificar_contrasena(
        credenciales.contrasena, usuario["contrasena_hash"] if usuario else None
    )
    if not contrasena_ok or not usuario["activo"]:
        raise _CREDENCIALES_INCORRECTAS

    roles = usuario["roles"]
    if credenciales.rol is not None:
        rol = credenciales.rol
    elif len(roles) == 1:
        rol = Rol(roles[0])
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La cuenta tiene varios roles: indica cuál usar en 'rol'",
        )
    if rol not in roles:
        raise _CREDENCIALES_INCORRECTAS

    token, vigencia = crear_token(usuario["id"], rol)
    return Token(access_token=token, expira_en=vigencia, rol_activo=rol)


@router.get("/me", response_model=UsuarioActual)
def yo(usuario: UsuarioAutenticado) -> UsuarioActual:
    return usuario
