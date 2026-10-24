"""Crea el primer ADMINISTRADOR. Solo funciona si todavía no existe ninguno.

Uso (desde vinculo/backend/, con la base levantada):
    uv run python -m scripts.crear_admin <correo> "<nombre completo>"

La contraseña se pide sin eco; nunca va en argumentos ni en variables de entorno.
"""

import sys
from getpass import getpass

from psycopg.rows import dict_row
from pydantic import ValidationError

from src.core.seguridad import hashear_contrasena
from src.db import usuarios as repo
from src.db.connection import get_connection
from src.schemas.auth import NuevoUsuario, Rol


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    correo, nombre = sys.argv[1], sys.argv[2]

    contrasena = getpass("Contraseña (12 a 72 bytes): ")
    if contrasena != getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1
    try:
        nuevo = NuevoUsuario(
            correo=correo, nombre_completo=nombre, contrasena=contrasena, roles=[Rol.ADMINISTRADOR]
        )
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 1

    with get_connection() as db:
        db.row_factory = dict_row
        if db.execute("SELECT 1 FROM usuarios WHERE 'ADMINISTRADOR' = ANY(roles)").fetchone():
            print("Ya existe un administrador; las demás cuentas se crean con POST /auth/register.",
                  file=sys.stderr)
            return 1
        usuario = repo.crear(
            db, nuevo.correo, nuevo.nombre_completo, hashear_contrasena(nuevo.contrasena),
            [Rol.ADMINISTRADOR.value],
        )
    print(f"Administrador creado: {usuario['correo']} ({usuario['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
