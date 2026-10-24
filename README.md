# TC4016-03 — VÍNCULO (Equipo 3)

Repositorio del equipo para TC4016 — Análisis, Diseño y Construcción de Software.
VÍNCULO convierte una sábana telefónica (CDR) en un patrón de vida analizable.
Solo metadatos y solo datos sintéticos.

| Carpeta | Contenido |
|---|---|
| `backend/` | API en FastAPI: autenticación JWT (`/auth/register`, `/auth/login`, `/auth/me`) y CRUD de `/casos` protegido por rol |
| `S05_S06_A1/` | `esquema_bd.sql` (PostgreSQL 18 + PostGIS) y `openapi_equipo.yaml` con `securitySchemes: BearerAuth` |
| `S05_S06_A2/` | `revision_seguridad.md`, `pruebas_auth.mp4` y la colección de Postman |

## Levantar el backend

Requiere [uv](https://docs.astral.sh/uv/) y una base PostgreSQL con `S05_S06_A1/esquema_bd.sql` aplicado.

```bash
cd backend
cp .env.example .env          # completar VINCULO_DATABASE_URL y JWT_SECRET (openssl rand -base64 48)
uv sync
uv run python -m scripts.crear_admin admin@vinculo.example "Administrador"
uv run uvicorn src.main:app --reload
```

Documentación interactiva en `http://127.0.0.1:8000/docs`.
