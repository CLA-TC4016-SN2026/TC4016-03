"""Consulta de usuarios para asignar casos. Solo coordinador (`x-roles`)."""


from fastapi import APIRouter, Depends

from src.api.deps import requiere_roles
from src.db import usuarios as repo
from src.db.connection import Db
from src.schemas.auth import Rol
from src.schemas.usuarios import UsuarioResumen

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get(
    "",
    response_model=list[UsuarioResumen],
    dependencies=[Depends(requiere_roles(Rol.COORDINADOR))],
)
def listar_usuarios(
    db: Db, rol: Rol | None = None
) -> list[dict]:
    """Cuentas activas; `rol` filtra, por ejemplo, los analistas disponibles."""
    return repo.listar_activos(db, rol)
