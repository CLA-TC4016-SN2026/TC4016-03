-- =====================================================================
-- VÍNCULO — Esquema físico, versión inicial generada por el agente (v1)
-- Insumos: diagrama_clases_equipo.puml y openapi_equipo.yaml (S05-S06-A1).
-- Manejador: PostgreSQL 18 + PostGIS.
-- Se conserva sin cambios como evidencia; la versión revisada es esquema_bd.sql
-- y las correcciones están en revision_sql.md.
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------- Enumeraciones ----------
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
    correo             varchar(254) NOT NULL UNIQUE,
    nombre_completo    varchar(200) NOT NULL,
    contrasena_hash    varchar(60)  NOT NULL,
    roles              rol[]        NOT NULL,
    intentos_fallidos  integer      NOT NULL DEFAULT 0,
    bloqueado_hasta    timestamptz,
    activo             boolean      NOT NULL DEFAULT true,
    creado_en          timestamptz  NOT NULL DEFAULT now()
);

-- ---------- Casos ----------
CREATE TABLE casos (
    folio             varchar(15) PRIMARY KEY,
    numero_solicitud  varchar(50) NOT NULL,
    estado            estado_caso NOT NULL DEFAULT 'ABIERTO',
    creado_por        uuid        NOT NULL REFERENCES usuarios (id),
    creado_en         timestamptz NOT NULL DEFAULT now(),
    cerrado_en        timestamptz,
    conservar_hasta   date
);

CREATE TABLE lineas_objetivo (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio  varchar(15) NOT NULL REFERENCES casos (folio) ON DELETE CASCADE,
    msisdn      varchar(15) NOT NULL,
    UNIQUE (caso_folio, msisdn)
);

CREATE TABLE asignaciones (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio  varchar(15)        NOT NULL REFERENCES casos (folio) ON DELETE CASCADE,
    usuario_id  uuid               NOT NULL REFERENCES usuarios (id),
    funcion     funcion_asignacion NOT NULL,
    desde       timestamptz        NOT NULL DEFAULT now(),
    hasta       timestamptz
);

-- ---------- Perfiles de concesionario ----------
CREATE TABLE perfiles_concesionario (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          varchar(100) NOT NULL,
    concesionario   varchar(100) NOT NULL,
    propietario_id  uuid NOT NULL REFERENCES usuarios (id),
    copiado_de      uuid REFERENCES perfiles_concesionario (id)
);

CREATE TABLE versiones_perfil (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id            uuid NOT NULL REFERENCES perfiles_concesionario (id) ON DELETE CASCADE,
    numero               integer NOT NULL,
    creada_en            timestamptz NOT NULL DEFAULT now(),
    encabezados          text[],
    mapeo_columnas       jsonb NOT NULL,
    contraparte          jsonb,
    codificacion         varchar(20) NOT NULL DEFAULT 'UTF-8',
    separador            char(1),
    formato_fecha        varchar(30) NOT NULL,
    formato_hora         varchar(30) NOT NULL,
    unidad_duracion      varchar(10) NOT NULL,
    formato_coordenadas  varchar(10),
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
    caso_folio       varchar(15)  NOT NULL REFERENCES casos (folio) ON DELETE CASCADE,
    tipo             tipo_archivo NOT NULL,
    numero_oficio    varchar(100) NOT NULL,
    concesionario    varchar(100) NOT NULL,
    fecha_recepcion  date         NOT NULL,
    sha256           char(64)     NOT NULL,
    nombre_original  varchar(255) NOT NULL,
    registrado_en    timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE cargas (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    archivo_id             uuid NOT NULL REFERENCES archivos (id) ON DELETE CASCADE,
    version_perfil_id      uuid NOT NULL REFERENCES versiones_perfil (id),
    estado                 estado_carga NOT NULL DEFAULT 'PREPARADA',
    error                  text,
    zona_horaria           varchar(64) NOT NULL,
    iniciada_en            timestamptz NOT NULL DEFAULT now(),
    concluida_en           timestamptz,
    renglones_originales   integer,
    campos_no_disponibles  text[]
);

CREATE TABLE renglones_no_interpretables (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    carga_id        uuid NOT NULL REFERENCES cargas (id) ON DELETE CASCADE,
    numero_renglon  integer NOT NULL,
    motivo          text NOT NULL
);

CREATE TABLE radiobases (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    catalogo_id    uuid REFERENCES archivos (id),
    concesionario  varchar(100) NOT NULL,
    cell_id        varchar(50),
    latitud        numeric(9, 6) NOT NULL,
    longitud       numeric(9, 6) NOT NULL,
    azimut         smallint
);

-- ---------- Eventos ----------
CREATE TABLE eventos (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    carga_id                 uuid NOT NULL REFERENCES cargas (id) ON DELETE CASCADE,
    linea_objetivo_id        uuid NOT NULL REFERENCES lineas_objetivo (id),
    fecha_hora_utc           timestamptz NOT NULL,
    tipo                     tipo_evento NOT NULL,
    direccion                direccion,
    resultado                resultado,
    duracion_seg             integer,
    contraparte_original     varchar(50),
    contraparte_normalizada  varchar(15),
    contraparte_numerica     boolean NOT NULL,
    imei                     varchar(16),
    imsi                     varchar(15),
    numero_renglon           integer NOT NULL,
    marca                    marca_duplicado,
    excluido                 boolean NOT NULL DEFAULT false,
    -- UbicacionReportada (objeto de valor)
    latitud                  numeric(9, 6),
    longitud                 numeric(9, 6),
    azimut                   smallint,
    cell_id                  varchar(50),
    lac_tac                  varchar(20),
    radiobase_id             uuid REFERENCES radiobases (id)
);

-- ---------- Análisis ----------
CREATE TABLE productos_analisis (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    caso_folio         varchar(15)   NOT NULL REFERENCES casos (folio) ON DELETE CASCADE,
    tipo               tipo_producto NOT NULL,
    parametros         jsonb         NOT NULL,
    rango_fechas       tstzrange,
    zona_presentacion  varchar(64)   NOT NULL,
    calculado_en       timestamptz   NOT NULL DEFAULT now()
);

CREATE TABLE producto_lineas (
    producto_id  uuid REFERENCES productos_analisis (id) ON DELETE CASCADE,
    linea_id     uuid REFERENCES lineas_objetivo (id),
    PRIMARY KEY (producto_id, linea_id)
);

CREATE TABLE producto_eventos (
    producto_id  uuid   REFERENCES productos_analisis (id) ON DELETE CASCADE,
    evento_id    bigint REFERENCES eventos (id),
    PRIMARY KEY (producto_id, evento_id)
);

CREATE TABLE zonas_cobertura (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id   uuid NOT NULL REFERENCES productos_analisis (id) ON DELETE CASCADE,
    radiobase_id  uuid NOT NULL REFERENCES radiobases (id),
    entorno       entorno NOT NULL,
    radio_m       integer NOT NULL,
    forma         forma_zona NOT NULL,
    geometria     geometry(Polygon, 4326) NOT NULL
);

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
    sha256_pdf         char(64) NOT NULL,
    sha256_xlsx        char(64) NOT NULL,
    regenerado_de      varchar(30) REFERENCES dictamenes (folio_exportacion)
);

CREATE TABLE dictamen_productos (
    folio_exportacion  varchar(30) REFERENCES dictamenes (folio_exportacion),
    producto_id        uuid REFERENCES productos_analisis (id),
    PRIMARY KEY (folio_exportacion, producto_id)
);

-- ---------- Trazabilidad ----------
CREATE TABLE entradas_bitacora (
    secuencia      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha_hora     timestamptz NOT NULL DEFAULT now(),
    usuario_id     uuid REFERENCES usuarios (id),
    rol_ejercido   rol,
    caso_folio     varchar(15) REFERENCES casos (folio),
    tipo_accion    varchar(50) NOT NULL,
    parametros     jsonb,
    hash_anterior  char(64),
    hash           char(64) NOT NULL
);

CREATE TABLE sellos_diarios (
    fecha                date PRIMARY KEY,
    entrada_secuencia    bigint NOT NULL REFERENCES entradas_bitacora (secuencia),
    hash_ultima_entrada  char(64) NOT NULL
);

CREATE TABLE valores_fabrica (
    id                       smallint PRIMARY KEY DEFAULT 1,
    franja_nocturna          jsonb NOT NULL,
    franja_laboral           jsonb NOT NULL,
    radio_urbano_m           integer NOT NULL,
    radio_rural_m            integer NOT NULL,
    distancia_urbana_m       integer NOT NULL,
    ventana_coubicacion_min  integer NOT NULL,
    distancia_coubicacion_m  integer NOT NULL,
    umbral_silencio_h        integer NOT NULL,
    minimo_eventos_pernocta  integer NOT NULL
);

-- ---------- Índices ----------
CREATE INDEX idx_usuarios_correo ON usuarios (correo);
CREATE INDEX idx_asignaciones_usuario ON asignaciones (usuario_id);
CREATE INDEX idx_archivos_caso ON archivos (caso_folio);
CREATE INDEX idx_eventos_linea_fecha ON eventos (linea_objetivo_id, fecha_hora_utc);
CREATE INDEX idx_eventos_contraparte ON eventos (contraparte_normalizada);
CREATE INDEX idx_bitacora_caso ON entradas_bitacora (caso_folio);

COMMIT;
