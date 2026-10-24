-- Esquema de VÍNCULO para autenticación y casos (S05-S06).
-- Corre solo al crear el volumen vacío. En un volumen existente se aplica a mano:
--   docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < postgres/init/02_esquema_bd.sql
--
-- Alcance: usuarios y casos. Las líneas objetivo, archivos, cargas y eventos del contrato
-- (S04_A2/openapi.yaml) llegan con sus propias actividades.

BEGIN;

-- Roles del contrato más ADMINISTRADOR, que solo gestiona cuentas (S-07) y no ve casos.
CREATE TYPE rol AS ENUM ('ADMINISTRADOR', 'COORDINADOR', 'ANALISTA', 'MP_PERITO', 'AUDITOR');

CREATE TYPE estado_caso AS ENUM ('ABIERTO', 'CERRADO');

CREATE TABLE usuarios (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    correo           text        NOT NULL CHECK (correo = btrim(correo) AND correo LIKE '%_@_%'),
    nombre_completo  text        NOT NULL CHECK (length(btrim(nombre_completo)) > 0),
    -- Hash bcrypt (incluye algoritmo, costo y sal). Nunca la contraseña.
    contrasena_hash  text        NOT NULL,
    -- Un usuario puede tener varios roles (D-1, S04-A1).
    roles            rol[]       NOT NULL CHECK (cardinality(roles) > 0),
    activo           boolean     NOT NULL DEFAULT true,
    creado_en        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX usuarios_correo_unico ON usuarios (lower(correo));

CREATE SEQUENCE casos_folio_seq;

CREATE TABLE casos (
    folio              text        PRIMARY KEY
                       DEFAULT 'C-' || lpad(nextval('casos_folio_seq')::text, 6, '0'),
    numero_solicitud   text        NOT NULL CHECK (length(btrim(numero_solicitud)) > 0),
    estado             estado_caso NOT NULL DEFAULT 'ABIERTO',
    mp_solicitante_id  uuid        NOT NULL REFERENCES usuarios (id),
    analista_id        uuid        REFERENCES usuarios (id),
    creado_en          timestamptz NOT NULL DEFAULT now(),
    cerrado_en         timestamptz,
    CHECK ((estado = 'CERRADO') = (cerrado_en IS NOT NULL))
);

ALTER SEQUENCE casos_folio_seq OWNED BY casos.folio;

CREATE INDEX casos_analista_idx ON casos (analista_id);

COMMIT;
