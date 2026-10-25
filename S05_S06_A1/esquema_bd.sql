-- =====================================================================
-- VÍNCULO — Esquema físico de la base de datos (Equipo 3, S05-S06-A1)
-- Manejador: PostgreSQL 18 + PostGIS.
-- Fuente: diagrama_clases_equipo.puml y openapi_equipo.yaml.
-- Parte de la versión del agente (esquema_bd_v1_agente.sql); las correcciones R-1..R-19
-- están justificadas en revision_sql.md.
--
-- Reglas de dominio que el esquema hace cumplir:
--   RD-01  ninguna tabla guarda contenido de comunicaciones (texto de SMS, audio).
--   RD-04  la radiobase es zona de cobertura: las zonas son polígonos; la coordenada de la
--          antena solo sirve para calcularlas.
--   RNF-05 la bitácora es de solo agregar.
--   O-4    un caso no se borra: se cierra y queda de solo lectura (cadena de custodia).
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------- Enumeraciones (mismos valores que openapi_equipo.yaml) ----------
CREATE TYPE rol AS ENUM ('ADMINISTRADOR', 'COORDINADOR', 'ANALISTA', 'MP_PERITO', 'AUDITOR');
CREATE TYPE estado_caso AS ENUM ('ABIERTO', 'CERRADO');
CREATE TYPE funcion_asignacion AS ENUM ('MP_SOLICITANTE', 'ANALISTA', 'PERITO');
CREATE TYPE tipo_archivo AS ENUM ('SABANA', 'CATALOGO');
CREATE TYPE estado_carga AS ENUM ('PREPARADA', 'CONFIRMADA', 'EN_PROCESO', 'CONCLUIDA', 'FALLIDA', 'CANCELADA');
CREATE TYPE tipo_evento AS ENUM ('VOZ', 'SMS', 'DATOS');
CREATE TYPE direccion AS ENUM ('ENTRANTE', 'SALIENTE');
CREATE TYPE resultado AS ENUM ('CONTESTADA', 'NO_CONTESTADA');
CREATE TYPE marca_duplicado AS ENUM ('DUPLICADO_EXACTO', 'FRAGMENTO_SESION');
CREATE TYPE tipo_producto AS ENUM ('CONTACTOS', 'PERNOCTA', 'DESPLAZAMIENTO', 'IDENTIFICADORES',
    'RUPTURAS', 'ACTIVIDAD_DIURNA', 'VENTANA_ACTIVIDAD', 'GRAFO', 'LINEA_TIEMPO', 'MAPA_AREAS',
    'COUBICACION', 'INTERMEDIARIOS');
CREATE TYPE entorno AS ENUM ('URBANA', 'RURAL');
CREATE TYPE forma_zona AS ENUM ('CIRCULO', 'SECTOR_120');

-- ---------- Acceso ----------
CREATE TABLE usuarios (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    correo             varchar(254) NOT NULL CHECK (correo = btrim(correo) AND correo LIKE '%_@_%'),
    nombre_completo    varchar(200) NOT NULL CHECK (btrim(nombre_completo) <> ''),
    -- Hash bcrypt (algoritmo, costo y sal). Nunca la contraseña.
    contrasena_hash    text         NOT NULL,
    -- D-1: un usuario puede tener varios roles; al menos uno (R-2).
    roles              rol[]        NOT NULL CHECK (cardinality(roles) > 0),
    intentos_fallidos  integer      NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
    bloqueado_hasta    timestamptz,
    activo             boolean      NOT NULL DEFAULT true,
    creado_en          timestamptz  NOT NULL DEFAULT now()
);
-- R-1: el correo es único sin distinguir mayúsculas.
CREATE UNIQUE INDEX usuarios_correo_unico ON usuarios (lower(correo));
-- GET /usuarios?rol=… filtra por rol.
CREATE INDEX usuarios_roles_idx ON usuarios USING gin (roles);

-- ---------- Casos ----------
-- R-3: el folio lo genera la base con el formato del contrato (VIN-AAAA-NNNNNN, O-9).
CREATE SEQUENCE casos_folio_seq;

CREATE TABLE casos (
    folio             varchar(15) PRIMARY KEY
                      DEFAULT 'VIN-' || to_char(now() AT TIME ZONE 'America/Mexico_City', 'YYYY')
                              || '-' || lpad(nextval('casos_folio_seq')::text, 6, '0')
                      CHECK (folio ~ '^VIN-\d{4}-\d{6}$'),
    numero_solicitud  varchar(50) NOT NULL CHECK (btrim(numero_solicitud) <> ''),
    estado            estado_caso NOT NULL DEFAULT 'ABIERTO',
    creado_por        uuid        NOT NULL REFERENCES usuarios (id),
    creado_en         timestamptz NOT NULL DEFAULT now(),
    cerrado_en        timestamptz,
    -- Plazo de conservación (S-13); se fija al cerrar.
    conservar_hasta   date,
    -- R-4: solo un caso cerrado tiene fecha de cierre.
    CHECK ((estado = 'CERRADO') = (cerrado_en IS NOT NULL)),
    CHECK (conservar_hasta IS NULL OR estado = 'CERRADO')
);
ALTER SEQUENCE casos_folio_seq OWNED BY casos.folio;

-- R-9: ninguna tabla hija de casos borra en cascada (RESTRICT por omisión).
CREATE TABLE lineas_objetivo (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio  varchar(15) NOT NULL REFERENCES casos (folio),
    -- R-6: E.164 con '+', hasta 15 dígitos (RF-23).
    msisdn      varchar(16) NOT NULL CHECK (msisdn ~ '^\+[1-9]\d{6,14}$'),
    UNIQUE (caso_folio, msisdn)
);

CREATE TABLE asignaciones (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio  varchar(15)        NOT NULL REFERENCES casos (folio),
    usuario_id  uuid               NOT NULL REFERENCES usuarios (id),
    funcion     funcion_asignacion NOT NULL,
    desde       timestamptz        NOT NULL DEFAULT now(),
    -- Historial: al reasignar se cierra la vigente (RNF-03).
    hasta       timestamptz,
    CHECK (hasta IS NULL OR hasta >= desde)
);
-- R-5: un solo analista y un solo MP solicitante vigentes por caso; un perito no se repite.
CREATE UNIQUE INDEX asignaciones_analista_vigente ON asignaciones (caso_folio)
    WHERE funcion = 'ANALISTA' AND hasta IS NULL;
CREATE UNIQUE INDEX asignaciones_mp_vigente ON asignaciones (caso_folio)
    WHERE funcion = 'MP_SOLICITANTE' AND hasta IS NULL;
CREATE UNIQUE INDEX asignaciones_perito_vigente ON asignaciones (caso_folio, usuario_id)
    WHERE funcion = 'PERITO' AND hasta IS NULL;
-- «Mis casos»: asignaciones vigentes de un usuario (RNF-02).
CREATE INDEX asignaciones_usuario_vigente ON asignaciones (usuario_id) WHERE hasta IS NULL;
CREATE INDEX asignaciones_caso_idx ON asignaciones (caso_folio);

-- R-17: máximo 20 líneas por caso y ninguna en un caso cerrado (RF-02, RF-27-AC-1).
-- Bloquea la fila del caso para que dos altas simultáneas no superen el límite.
CREATE FUNCTION lineas_objetivo_validar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_estado estado_caso;
BEGIN
    SELECT estado INTO v_estado FROM casos WHERE folio = NEW.caso_folio FOR UPDATE;
    IF v_estado = 'CERRADO' THEN
        RAISE EXCEPTION 'El caso % está cerrado', NEW.caso_folio USING ERRCODE = 'check_violation';
    END IF;
    IF (SELECT count(*) FROM lineas_objetivo WHERE caso_folio = NEW.caso_folio) >= 20 THEN
        RAISE EXCEPTION 'El caso % ya tiene 20 líneas objetivo', NEW.caso_folio
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER lineas_objetivo_validar BEFORE INSERT ON lineas_objetivo
    FOR EACH ROW EXECUTE FUNCTION lineas_objetivo_validar();

-- ---------- Perfiles de concesionario (RF-29) ----------
CREATE TABLE perfiles_concesionario (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          varchar(100) NOT NULL CHECK (btrim(nombre) <> ''),
    concesionario   varchar(100) NOT NULL CHECK (btrim(concesionario) <> ''),
    propietario_id  uuid NOT NULL REFERENCES usuarios (id),
    copiado_de      uuid REFERENCES perfiles_concesionario (id)
);
CREATE INDEX perfiles_propietario_idx ON perfiles_concesionario (propietario_id);

-- Cada edición crea una versión nueva e inmutable (RF-29-AC-4).
CREATE TABLE versiones_perfil (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id            uuid NOT NULL REFERENCES perfiles_concesionario (id),
    numero               integer NOT NULL CHECK (numero >= 1),
    creada_en            timestamptz NOT NULL DEFAULT now(),
    -- R-15: el contrato exige VersionPerfil.creadaPor.
    creada_por           uuid NOT NULL REFERENCES usuarios (id),
    encabezados          text[],
    mapeo_columnas       jsonb NOT NULL CHECK (jsonb_typeof(mapeo_columnas) = 'object'),
    contraparte          jsonb CHECK (contraparte IS NULL OR jsonb_typeof(contraparte) = 'object'),
    -- R-16: mismos valores que los enums del contrato.
    codificacion         varchar(12) NOT NULL DEFAULT 'UTF-8'
                         CHECK (codificacion IN ('UTF-8', 'WINDOWS-1252', 'ISO-8859-1')),
    separador            char(1),
    formato_fecha        varchar(30) NOT NULL,
    formato_hora         varchar(30) NOT NULL,
    unidad_duracion      varchar(8)  NOT NULL CHECK (unidad_duracion IN ('SEGUNDOS', 'MINUTOS')),
    formato_coordenadas  varchar(7)  CHECK (formato_coordenadas IN ('DECIMAL', 'GMS')),
    entrega_coordenadas  boolean NOT NULL,
    UNIQUE (perfil_id, numero)
);

CREATE TABLE traducciones_tipo (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version_perfil_id    uuid NOT NULL REFERENCES versiones_perfil (id) ON DELETE CASCADE,
    valor_concesionario  varchar(100) NOT NULL,
    tipo                 tipo_evento NOT NULL,
    direccion            direccion,
    resultado            resultado,
    UNIQUE (version_perfil_id, valor_concesionario)
);

-- ---------- Ingesta ----------
CREATE TABLE archivos (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio       varchar(15)  NOT NULL REFERENCES casos (folio),
    tipo             tipo_archivo NOT NULL,
    numero_oficio    varchar(100) NOT NULL CHECK (btrim(numero_oficio) <> ''),
    concesionario    varchar(100) NOT NULL CHECK (btrim(concesionario) <> ''),
    fecha_recepcion  date         NOT NULL,
    -- R-8: SHA-256 en hexadecimal, como el patrón del contrato.
    sha256           char(64)     NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    nombre_original  varchar(255) NOT NULL,
    registrado_en    timestamptz  NOT NULL DEFAULT now()
);
-- Sin UNIQUE: un duplicado se admite si se confirma (RF-03-AC-5); el índice lo detecta.
CREATE INDEX archivos_caso_hash_idx ON archivos (caso_folio, sha256);

CREATE TABLE cargas (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    archivo_id             uuid NOT NULL REFERENCES archivos (id),
    version_perfil_id      uuid NOT NULL REFERENCES versiones_perfil (id),
    estado                 estado_carga NOT NULL DEFAULT 'PREPARADA',
    error                  text,
    zona_horaria           varchar(64) NOT NULL,
    iniciada_en            timestamptz NOT NULL DEFAULT now(),
    concluida_en           timestamptz,
    renglones_originales   integer CHECK (renglones_originales >= 0),
    campos_no_disponibles  text[],
    -- Solo una carga fallida tiene motivo de error (RNF-10).
    CHECK ((estado = 'FALLIDA') = (error IS NOT NULL))
);
CREATE INDEX cargas_archivo_idx ON cargas (archivo_id);

CREATE TABLE renglones_no_interpretables (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carga_id        uuid NOT NULL REFERENCES cargas (id) ON DELETE CASCADE,
    numero_renglon  integer NOT NULL CHECK (numero_renglon >= 1),
    motivo          text NOT NULL
);
CREATE INDEX renglones_carga_idx ON renglones_no_interpretables (carga_id);

-- RD-04: la coordenada de la antena solo sirve para calcular la zona de cobertura.
CREATE TABLE radiobases (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    catalogo_id    uuid REFERENCES archivos (id),
    concesionario  varchar(100) NOT NULL,
    cell_id        varchar(50),
    latitud        numeric(9, 6) NOT NULL CHECK (latitud BETWEEN -90 AND 90),
    longitud       numeric(9, 6) NOT NULL CHECK (longitud BETWEEN -180 AND 180),
    azimut         smallint CHECK (azimut BETWEEN 0 AND 359)
);
CREATE INDEX radiobases_catalogo_idx ON radiobases (catalogo_id);

-- ---------- Eventos (RD-01: solo metadatos) ----------
CREATE TABLE eventos (
    -- R-13: uuid, como Evento.id del contrato.
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carga_id                 uuid NOT NULL REFERENCES cargas (id),
    linea_objetivo_id        uuid NOT NULL REFERENCES lineas_objetivo (id),
    fecha_hora_utc           timestamptz NOT NULL,
    tipo                     tipo_evento NOT NULL,
    direccion                direccion,
    resultado                resultado,
    duracion_seg             integer CHECK (duracion_seg >= 0),
    contraparte_original     varchar(50),
    contraparte_normalizada  varchar(16) CHECK (contraparte_normalizada ~ '^\+[1-9]\d{6,14}$'),
    contraparte_numerica     boolean NOT NULL,
    imei                     varchar(16) CHECK (imei ~ '^\d{14,16}$'),
    imsi                     varchar(15) CHECK (imsi ~ '^\d{6,15}$'),
    numero_renglon           integer NOT NULL CHECK (numero_renglon >= 1),
    -- RF-06: los duplicados se marcan, nunca se borran.
    marca                    marca_duplicado,
    excluido                 boolean NOT NULL DEFAULT false,
    -- UbicacionReportada (objeto de valor): tal como la entrega el concesionario.
    latitud                  numeric(9, 6) CHECK (latitud BETWEEN -90 AND 90),
    longitud                 numeric(9, 6) CHECK (longitud BETWEEN -180 AND 180),
    azimut                   smallint CHECK (azimut BETWEEN 0 AND 359),
    cell_id                  varchar(50),
    lac_tac                  varchar(20),
    radiobase_id             uuid REFERENCES radiobases (id)
);
-- Orden estable por línea y fecha (RNF-11); ranking de contactos (RF-07).
CREATE INDEX eventos_linea_fecha_idx ON eventos (linea_objetivo_id, fecha_hora_utc, id);
CREATE INDEX eventos_contraparte_idx ON eventos (contraparte_normalizada);
CREATE INDEX eventos_carga_idx ON eventos (carga_id);

-- ---------- Análisis ----------
CREATE TABLE productos_analisis (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio         varchar(15)   NOT NULL REFERENCES casos (folio),
    tipo               tipo_producto NOT NULL,
    parametros         jsonb         NOT NULL,
    rango_fechas       tstzrange,
    zona_presentacion  varchar(64)   NOT NULL,
    calculado_en       timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX productos_caso_idx ON productos_analisis (caso_folio);

CREATE TABLE producto_lineas (
    producto_id  uuid REFERENCES productos_analisis (id) ON DELETE CASCADE,
    linea_id     uuid REFERENCES lineas_objetivo (id),
    PRIMARY KEY (producto_id, linea_id)
);
CREATE INDEX producto_lineas_linea_idx ON producto_lineas (linea_id);

-- RF-16: eventos que producen cada resultado.
CREATE TABLE producto_eventos (
    producto_id  uuid REFERENCES productos_analisis (id) ON DELETE CASCADE,
    evento_id    uuid REFERENCES eventos (id),
    PRIMARY KEY (producto_id, evento_id)
);
CREATE INDEX producto_eventos_evento_idx ON producto_eventos (evento_id);

-- RD-04: zona de cobertura como polígono, nunca como punto.
CREATE TABLE zonas_cobertura (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id   uuid NOT NULL REFERENCES productos_analisis (id) ON DELETE CASCADE,
    radiobase_id  uuid NOT NULL REFERENCES radiobases (id),
    entorno       entorno NOT NULL,
    radio_m       integer NOT NULL CHECK (radio_m > 0),
    forma         forma_zona NOT NULL,
    geometria     geometry(Polygon, 4326) NOT NULL CHECK (ST_IsValid(geometria))
);
CREATE INDEX zonas_producto_idx ON zonas_cobertura (producto_id);

CREATE TABLE revisiones (
    producto_id     uuid PRIMARY KEY REFERENCES productos_analisis (id) ON DELETE CASCADE,
    coordinador_id  uuid NOT NULL REFERENCES usuarios (id),
    revisado_en     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dictamenes (
    folio_exportacion  varchar(30) PRIMARY KEY,
    caso_folio         varchar(15) NOT NULL REFERENCES casos (folio),
    exportado_por      uuid NOT NULL REFERENCES usuarios (id),
    exportado_en       timestamptz NOT NULL DEFAULT now(),
    sha256_pdf         char(64) NOT NULL CHECK (sha256_pdf ~ '^[a-f0-9]{64}$'),
    sha256_xlsx        char(64) NOT NULL CHECK (sha256_xlsx ~ '^[a-f0-9]{64}$'),
    -- RF-20: una regeneración apunta al dictamen original.
    regenerado_de      varchar(30) REFERENCES dictamenes (folio_exportacion)
);
CREATE INDEX dictamenes_caso_idx ON dictamenes (caso_folio);

CREATE TABLE dictamen_productos (
    folio_exportacion  varchar(30) REFERENCES dictamenes (folio_exportacion),
    producto_id        uuid REFERENCES productos_analisis (id),
    PRIMARY KEY (folio_exportacion, producto_id)
);
CREATE INDEX dictamen_productos_producto_idx ON dictamen_productos (producto_id);

-- ---------- Trazabilidad (RF-21, RF-22, RNF-05) ----------
CREATE TABLE entradas_bitacora (
    secuencia      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha_hora     timestamptz NOT NULL DEFAULT now(),
    usuario_id     uuid REFERENCES usuarios (id),
    rol_ejercido   rol,
    caso_folio     varchar(15) REFERENCES casos (folio),
    tipo_accion    varchar(50) NOT NULL,
    parametros     jsonb,
    hash_anterior  char(64) CHECK (hash_anterior ~ '^[a-f0-9]{64}$'),
    hash           char(64) NOT NULL CHECK (hash ~ '^[a-f0-9]{64}$')
);
CREATE INDEX bitacora_caso_idx ON entradas_bitacora (caso_folio);
CREATE INDEX bitacora_usuario_idx ON entradas_bitacora (usuario_id);

-- R-7: la bitácora es de solo agregar; ni UPDATE, ni DELETE, ni TRUNCATE.
CREATE FUNCTION bitacora_solo_agregar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora es de solo agregar (RNF-05)' USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER bitacora_sin_cambios BEFORE UPDATE OR DELETE ON entradas_bitacora
    FOR EACH ROW EXECUTE FUNCTION bitacora_solo_agregar();
CREATE TRIGGER bitacora_sin_truncate BEFORE TRUNCATE ON entradas_bitacora
    FOR EACH STATEMENT EXECUTE FUNCTION bitacora_solo_agregar();

CREATE TABLE sellos_diarios (
    fecha                date PRIMARY KEY,
    entrada_secuencia    bigint NOT NULL REFERENCES entradas_bitacora (secuencia),
    hash_ultima_entrada  char(64) NOT NULL CHECK (hash_ultima_entrada ~ '^[a-f0-9]{64}$')
);

-- ---------- Configuración (S-08, RF-28) ----------
-- R-10: una sola fila vigente. R-18: franjas como hora local (Franja del contrato: HH:MM).
-- S-08 limita la franja laboral a lunes-viernes; el contrato aún no modela los días.
CREATE TABLE valores_fabrica (
    id                       smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    franja_nocturna_inicio   time    NOT NULL,
    franja_nocturna_fin      time    NOT NULL,
    franja_laboral_inicio    time    NOT NULL,
    franja_laboral_fin       time    NOT NULL,
    radio_urbano_m           integer NOT NULL CHECK (radio_urbano_m > 0),
    radio_rural_m            integer NOT NULL CHECK (radio_rural_m > 0),
    distancia_urbana_m       integer NOT NULL CHECK (distancia_urbana_m > 0),
    ventana_coubicacion_min  integer NOT NULL CHECK (ventana_coubicacion_min > 0),
    distancia_coubicacion_m  integer NOT NULL CHECK (distancia_coubicacion_m > 0),
    -- R-19: number en el contrato (admite fracciones de hora).
    umbral_silencio_h        numeric(5, 2) NOT NULL CHECK (umbral_silencio_h > 0),
    minimo_eventos_pernocta  integer NOT NULL CHECK (minimo_eventos_pernocta > 0)
);
-- Valores de fábrica de S-08 (SRS_equipo.md).
INSERT INTO valores_fabrica (franja_nocturna_inicio, franja_nocturna_fin, franja_laboral_inicio,
    franja_laboral_fin, radio_urbano_m, radio_rural_m, distancia_urbana_m, ventana_coubicacion_min,
    distancia_coubicacion_m, umbral_silencio_h, minimo_eventos_pernocta)
VALUES ('22:00', '06:00', '09:00', '18:00', 1000, 5000, 2000, 15, 500, 12, 10);

COMMIT;
