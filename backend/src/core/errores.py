"""Errores de la API en formato RFC 9457 (`application/problem+json`), criterio O-6 del contrato.

- 400: la forma de la petición es inválida (JSON, tipos, campos desconocidos, enumeraciones).
- 422: la forma es válida pero viola una regla del dominio; incluye los datos obligatorios
  ausentes ("Faltan: …", RF-02-AC-2).
- 409: la operación no es compatible con el estado del recurso (caso cerrado).
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_MEDIA = "application/problem+json"
_log = logging.getLogger("vinculo")

# Nombre que ve el usuario para cada campo obligatorio (RF-02-AC-2).
_ETIQUETAS = {
    "numeroSolicitud": "número de solicitud",
    "mpSolicitanteId": "MP solicitante",
    "lineas": "líneas objetivo",
    "msisdn": "número de la línea",
    "usuarioId": "usuario",
}
_TITULOS_HTTP = {404: "Recurso no encontrado", 405: "Método no permitido"}


class ErrorDominio(Exception):
    def __init__(
        self,
        estado: int,
        titulo: str,
        detalle: str | None = None,
        errores: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(titulo)
        self.estado = estado
        self.titulo = titulo
        self.detalle = detalle
        self.errores = errores


def no_procesable(titulo: str, campo: str | None = None) -> ErrorDominio:
    errores = [{"campo": campo, "mensaje": titulo}] if campo else None
    return ErrorDominio(status.HTTP_422_UNPROCESSABLE_CONTENT, titulo, errores=errores)


def conflicto(titulo: str) -> ErrorDominio:
    return ErrorDominio(status.HTTP_409_CONFLICT, titulo)


def no_encontrado(titulo: str) -> ErrorDominio:
    return ErrorDominio(status.HTTP_404_NOT_FOUND, titulo)


def _problema(
    estado: int,
    titulo: str,
    detalle: str | None = None,
    errores: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    cuerpo: dict[str, Any] = {"type": "about:blank", "title": titulo, "status": estado}
    if detalle:
        cuerpo["detail"] = detalle
    if errores:
        cuerpo["errores"] = errores
    return JSONResponse(cuerpo, status_code=estado, media_type=_MEDIA, headers=headers)


def _campo(loc: tuple[Any, ...]) -> str:
    return ".".join(str(p) for p in loc if p not in ("body", "query", "path"))


async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Un identificador de ruta mal formado nombra un recurso que no existe.
    if all(e["loc"][0] == "path" for e in exc.errors()):
        return _problema(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
    # Nunca se devuelve el valor rechazado ("input"): con una contraseña saldría en claro.
    faltantes, forma = [], []
    for e in exc.errors():
        campo = _campo(tuple(e["loc"]))
        if e["type"] == "missing" and campo:
            nombre = _ETIQUETAS.get(str(e["loc"][-1]), campo)
            faltantes.append({"campo": campo, "mensaje": f"Faltan: {nombre}"})
        else:
            forma.append({"campo": campo, "mensaje": e["msg"]} if campo else {"mensaje": e["msg"]})
    if forma:
        return _problema(status.HTTP_400_BAD_REQUEST, "Solicitud mal formada", errores=forma)
    return _problema(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "Faltan datos obligatorios", errores=faltantes
    )


async def _dominio(_: Request, exc: ErrorDominio) -> JSONResponse:
    return _problema(exc.estado, exc.titulo, exc.detalle, exc.errores)


async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Las excepciones del framework traen la frase estándar en inglés como detalle.
    titulo = exc.detail if isinstance(exc.detail, str) else "Error"
    if titulo == HTTPStatus(exc.status_code).phrase:
        titulo = _TITULOS_HTTP.get(exc.status_code, titulo)
    return _problema(exc.status_code, titulo, headers=getattr(exc, "headers", None))


async def _interno(_: Request, exc: Exception) -> JSONResponse:
    _log.exception("Error no previsto", exc_info=exc)
    return _problema(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(ErrorDominio, _dominio)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(Exception, _interno)
