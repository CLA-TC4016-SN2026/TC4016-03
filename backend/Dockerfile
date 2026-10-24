# Imagen de la API de VÍNCULO (FastAPI + Python 3.13).
#
# Dos etapas:
#   1. builder: uv instala las dependencias exactas de uv.lock en /app/.venv.
#   2. runtime: solo Python + el .venv + el código. Sin uv, sin caché, sin compiladores.
# Multi-arquitectura: la Mac la construye para arm64 y la VM para amd64.

# --- Etapa 1: dependencias ---------------------------------------------------
FROM python:3.13-slim-trixie AS builder

# uv fijado a la misma versión que en la Mac (0.12.19).
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Primero solo los archivos de dependencias: si el código cambia pero uv.lock no,
# Docker reutiliza esta capa y no reinstala nada.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# --- Etapa 2: ejecución ------------------------------------------------------
FROM python:3.13-slim-trixie AS runtime

# Usuario sin privilegios: si alguien compromete la API, no es root en el contenedor.
RUN groupadd --system vinculo && useradd --system --gid vinculo --home /app vinculo

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER vinculo
EXPOSE 8000

# La URL de la base llega por variable de entorno (VINCULO_DATABASE_URL), nunca en la imagen.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
