"""Hash de contraseñas (bcrypt) y emisión y verificación de JWT (PyJWT, HS256)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from src.core.config import get_settings

# Fijar el algoritmo evita la confusión de algoritmos ("alg": "none" o RS256 contra HS256).
_ALGORITMO = "HS256"
# 12 rondas = 2^12 iteraciones; el valor por omisión de la biblioteca, explícito aquí.
_RONDAS_BCRYPT = 12
# Hash de una contraseña que nadie conoce: se compara contra él cuando el correo no existe,
# para que esa respuesta tarde lo mismo que una contraseña incorrecta (RF-01-AC-3).
_HASH_SEÑUELO = bcrypt.hashpw(b"no-es-una-cuenta", bcrypt.gensalt(_RONDAS_BCRYPT))


class TokenInvalido(Exception):
    """Firma inválida, token expirado, mal formado o sin los claims obligatorios."""


def hashear_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt(_RONDAS_BCRYPT)).decode()


def verificar_contrasena(contrasena: str, hash_guardado: str | None) -> bool:
    """Compara en tiempo constante. Con `hash_guardado=None` gasta el mismo tiempo y devuelve False."""
    objetivo = hash_guardado.encode() if hash_guardado else _HASH_SEÑUELO
    try:
        coincide = bcrypt.checkpw(contrasena.encode(), objetivo)
    except ValueError:
        # Hash guardado que no es bcrypt (cuenta sin acceso) o contraseña de más de 72 bytes.
        bcrypt.checkpw(b"x", _HASH_SEÑUELO)
        return False
    return coincide and hash_guardado is not None


def crear_token(usuario_id: UUID, rol: str) -> tuple[str, int]:
    """Devuelve el JWT y su vigencia en segundos."""
    ajustes = get_settings()
    ahora = datetime.now(UTC)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(seconds=ajustes.jwt_expiration),
    }
    token = jwt.encode(claims, ajustes.jwt_secret.get_secret_value(), algorithm=_ALGORITMO)
    return token, ajustes.jwt_expiration


def decodificar_token(token: str) -> dict[str, Any]:
    """Verifica firma y expiración, y exige los claims; si algo falla lanza TokenInvalido."""
    try:
        return jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[_ALGORITMO],
            options={"require": ["sub", "rol", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as error:
        raise TokenInvalido from error
