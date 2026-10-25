# TC4016-03 — VÍNCULO (Equipo 3)

Repositorio del equipo para TC4016 — Análisis, Diseño y Construcción de Software.
VÍNCULO convierte una sábana telefónica (CDR) en un patrón de vida analizable.
Solo metadatos y solo datos sintéticos.

| Carpeta | Contenido |
|---|---|
| `backend/` | API en FastAPI con rutas, servicios y repositorios: autenticación JWT (`/auth/*`) y CRUD protegido por rol de usuarios, casos, líneas objetivo, asignaciones y perfiles de concesionario; errores RFC 9457 |
| `S05_S06_A1/` | Diseño consolidado (`openapi_equipo.yaml`, `diagrama_clases_equipo.puml`, `arquitectura_equipo.md`, `diferencias_diseno.md`), `esquema_bd.sql` (PostgreSQL 18 + PostGIS), `revision_sql.md`, `pruebas_postman.mp4` y la colección de Postman |
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

Con `uvicorn` las rutas cuelgan de la raíz (`http://127.0.0.1:8000/casos`). En la colección de
Postman, cambia `baseUrl` a `http://127.0.0.1:8000`; su valor por omisión,
`http://127.0.0.1:8080/api`, corresponde al despliegue con nginx.

Documentación interactiva en `http://127.0.0.1:8000/docs`.
