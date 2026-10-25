from uuid import UUID

from src.schemas.auth import Rol
from src.schemas.base import Esquema


class UsuarioResumen(Esquema):
    id: UUID
    nombre_completo: str
    roles: list[Rol]


class ReferenciaUsuario(Esquema):
    usuario_id: UUID
