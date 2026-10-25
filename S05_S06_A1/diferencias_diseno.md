# Análisis de diferencias de diseño — Equipo 3 (S05-S06-A1, Parte 0)

> **Estado:** versión 1.0 de equipo, 2026-10-24. Todos los conflictos están resueltos.
> **Artefactos resultantes:** `openapi_equipo.yaml`, `diagrama_clases_equipo.puml`,
> `arquitectura_equipo.md`.

## 1. Insumos, acuerdo y método

| Integrante | OpenAPI (S04-A2) | Clases (S04-A1) | Arquitectura (S04-A1) | Participación en la consolidación |
|---|---|---|---|---|
| José Benjamín Oviedo Morales (**JB**) | `openapi.yaml` v1.0.0: 38 rutas, 51 operaciones, 133 IDs de criterios | `diagrama_clases.puml` v2: 31 clases y 7 enums | ADR-001 a ADR-003 y C4 de contenedores y componentes | Autor de la base; decidió como PO los conflictos de dominio (O-4, C-2, O-3) |
| José Francisco González Vargas (**JF**) | — | — | — | Aprobó la base en la reunión del 2026-10-24. Su SRS (105 criterios de RF) es la mayor fuente de los IDs `x-acceptance-criteria` vía `SRS_equipo.md` |
| Francisco Leonardo Armendáriz Cavazos (**FA**) | — | — | — | Aprobó la base en la reunión del 2026-10-24 |
| Mario Sánchez Valtierra (**MS**) | — | — | — | Aprobó la base en la reunión del 2026-10-24 |

**Acuerdo del equipo.** En la reunión del 2026-10-24 los cuatro integrantes acordaron adoptar los
tres artefactos de JB como base, por ser los únicos construidos sobre el `SRS_equipo.md`
consolidado en S03-A1 y por estar ya parcialmente implementados en `backend/`. Los artefactos
individuales de JF, FA y MS no se usaron para el análisis documental.

**Qué se comparó.** Al no haber varias versiones del mismo artefacto, los conflictos reales
aparecen entre fuentes que deben coincidir:

1. El **contrato de S04** contra el **código ya construido** en S05-S06 (autenticación y casos).
2. El **diagrama de clases** contra los **schemas del contrato**, atributo por atributo.
3. La **arquitectura de S04** contra la estructura real de `backend/`.
4. Los permisos del contrato contra la matriz de **RNF-01** del `SRS_equipo.md`.

**Método.** El agente (Claude, en Cursor) extrajo las diferencias con scripts sobre los archivos
(no a ojo) y las clasificó como en S03-A1:

- **Consenso:** las fuentes coinciden.
- **Gap:** un elemento está en una fuente y falta en la otra.
- **Conflicto:** las dos fuentes lo definen de forma incompatible.

JB decidió los conflictos de dominio; las resoluciones técnicas se tomaron por coherencia con el
SRS y con lo ya entregado, y el equipo aprobó el resultado.

## 2. OpenAPI

**Consenso.** 48 de las 51 operaciones de S04 pasan sin cambios de ruta, método, cuerpo ni
códigos. Los **133 IDs** de criterios de S04 se conservan todos (verificado por script: 0
perdidos, 0 nuevos). Se mantienen las convenciones de S04: sustantivos en plural, acciones como
recursos, paginación por cursor y `409` para conflictos de estado.

| # | Tipo | S04 | Construido / SRS | Resolución y argumento |
|---|---|---|---|---|
| O-1 | Conflicto | Servidor `/api/v1`; FastAPI monta los routers con `/v1` | Rutas sin `/v1` | **`/api`**. El versionado en la ruta no aporta mientras haya un solo cliente (la SPA del mismo origen); cambiarlo rompería la A2 ya probada |
| O-2 | Conflicto | `POST /sesiones`, `GET` y `DELETE /sesiones/actual` | `/auth/register`, `/auth/login`, `/auth/me` | **`/auth/*`**, que exige la consigna de S05-S06. Desaparece el cierre de sesión: con JWT sin estado no hay sesión que cerrar (ver A-3) |
| O-3 | Conflicto | Login con `usuario` | Login con `correo` | **Correo** (decisión de JB). Es único y verificable con `email-validator`, y ya es la llave de la A2 |
| O-4 | Conflicto | Solo `PATCH /casos/{folio}` con `estado: CERRADO`; sin borrado | `PUT` y `DELETE /casos/{folio}` | **Como S04** (decisión de JB). Borrar un caso destruye su cadena de custodia; un caso solo se cierra y queda de solo lectura (RF-27-AC-1). Se eliminan `PUT` y `DELETE` del código |
| O-5 | Conflicto | `NuevoCaso` exige `lineas` (1 a 20) | `lineas` no existía | **Como S04**: un caso sin línea objetivo no tiene qué analizar (RF-02-AC-1) |
| O-6 | Gap | Roles `ANALISTA`, `COORDINADOR`, `MP_PERITO`, `AUDITOR` | Rol `ADMINISTRADOR` | **Se agrega.** Formaliza al administrador técnico de S-07: crea cuentas y no ve casos (separación de funciones) |
| O-7 | Gap | Contrato completo, con 133 IDs | El extracto de la A2 tenía 4 IDs | **Contrato completo** como base; el extracto se descarta |
| O-8 | Conflicto | Errores RFC 9457 (`application/problem+json`): `400` esquema, `422` dominio | `{"detail": …}` de FastAPI y `422` para todo | **Como S04.** El código adopta manejadores globales; el campo `detail` se conserva |
| O-9 | Conflicto | Folio `VIN-2026-000123` | Folio `C-000001` | **Como S04**: `VIN-AAAA-NNNNNN`, con el año de alta (patrón en `CasoResumen.folio`) |
| O-10 | Gap | Roles solo en descripciones y en parte de las operaciones | `x-roles` en cada operación (A2) | **`x-roles` en las 51 operaciones**, derivados de la matriz de RNF-01 y de RNF-02. Hace verificable por script que el código aplica la matriz |

`securitySchemes` cambia de `bearerAuth` a **`BearerAuth`**, el nombre que pide la consigna.

## 3. Diagrama de clases

**Consenso.** Las 19 clases con schema en el contrato coinciden en nombre, y los enums
`EstadoCaso`, `TipoEvento`, `Direccion`, `Resultado` y `MarcaDuplicado` tienen los mismos valores.
`TraduccionTipo`, `RenglonNoInterpretable` y `SelloDiario` coinciden atributo por atributo. El
diagrama consolidado queda con 30 clases (sale `Sesion`) y 8 enums (entra `EstadoCarga`).

| # | Tipo | Diagrama S04 | Contrato / código | Resolución y argumento |
|---|---|---|---|---|
| C-1 | Conflicto | `Usuario.nombreUsuario` | `correo` | **`correo : email {único}`**, por O-3. Se agrega `creadoEn`, que el contrato expone |
| C-2 | Conflicto | `Asignacion` como entidad (`funcion`, `desde`, `hasta`) | Columnas `mp_solicitante_id` y `analista_id` en `casos` | **Entidad** (decisión de JB). Admite varios peritos e historial de reasignaciones, y es lo que necesita RNF-03 (el analista anterior pierde el acceso) |
| C-3 | Gap | `Caso.conservarHasta` y relación `creadoPor` | La tabla de la A2 no los tenía | **Se conservan** en el diagrama y pasan al esquema (RF-27-AC-4, plazo de conservación) |
| C-4 | Gap | `Usuario.intentosFallidos`, `bloqueadoHasta` | Ausentes en la tabla | **Se conservan** y pasan al esquema; el bloqueo de RNF-15 sigue como deuda |
| C-5 | Gap | `VersionPerfil` sin `encabezados`, `contraparte`, `codificacion`, `separador` | `DefinicionPerfil` los exige | **Se agregan** al diagrama: definen cómo leer el archivo (RF-04-AC-4) |
| C-6 | Conflicto | Clase `Sesion` (`rolActivo`, `ultimaActividad`) guardada en el servidor | JWT sin estado con el rol activo como *claim* | **Se elimina `Sesion`.** D-1 y D-2 se cumplen con el *claim* `rol`; la relectura de la cuenta en cada petición cubre RNF-03. La expiración por inactividad queda como deuda |
| C-7 | Gap | `Carga` sin estado; `Dictamen` sin regeneración; `ValoresFabrica` incompleto | `Carga.estado` y `error`, `Dictamen.regeneradoDe`, tres valores de S-08 | **Se agregan**: enum `EstadoCarga` (6 valores), relación reflexiva `regeneradoDe` (RF-20) y `distanciaUrbanaM`, `ventanaCoubicacionMin`, `distanciaCoubicacionM` (S-08) |
| C-8 | Convención | Los `id` y las asociaciones no aparecen como atributos | El API los expone como campos | **Nota en el diagrama**: toda entidad tiene `id : uuid` salvo `Caso` (folio) y `Dictamen` (folio de exportación); las asociaciones aparecen en el API como campos; los campos calculados no se persisten |

**Coherencia con el contrato (verificada por script).** Tras C-1 a C-8, los 19 pares clase ↔
schema quedan sin diferencias sin explicar. Lo que el API tiene y la clase no es un `id`, una
asociación o un campo calculado. Lo que la clase tiene y el API no es interno a propósito, como
`hashContrasena`, o es historial (`Asignacion.hasta`).

## 4. Arquitectura

**Consenso.** Se mantiene ADR-001 (monolito modular en capas + worker, cola en PostgreSQL),
ADR-002 (patrones) y ADR-003 (on-premise), con los mismos contenedores.

| # | Tipo | S04 | Construido | Resolución y argumento |
|---|---|---|---|---|
| A-1 | Conflicto | Routers → **servicios** → repositorios con `Protocol` | Routers → repositorios, sin servicios | **Se agrega la capa de servicios** (`backend/src/services/`). Las reglas (máximo 20 líneas, solo se cierra un caso abierto, visibilidad por asignación) dejan de vivir en el router. Los `Protocol` se difieren a S09, cuando las pruebas necesiten dobles |
| A-2 | Gap | Worker y almacén de originales | No construidos | **Siguen planeados**: ninguna operación de esta etapa encola trabajos. Se marcan punteados en el diagrama |
| A-3 | Conflicto | Componente «sesión» con estado | JWT HS256 sin estado, `bcrypt`, dependencias `usuario_actual` y `requiere_roles` | **JWT**, por C-6. Aparecen como componentes nuevos «Autenticación», «Autorización» y «Errores RFC 9457» |

## 5. Impacto en lo ya entregado

- **S05-S06-A2:** su tabla de rutas protegidas listaba `PUT` y `DELETE /casos/{folio}`. Con O-4,
  esas rutas dejan de existir y la protección se verifica de nuevo contra este contrato.
- **Esquema:** C-2, C-3, C-4 y O-9 cambian las tablas `usuarios` y `casos` de la A2. El esquema
  completo se genera en la Parte 1 a partir de `diagrama_clases_equipo.puml`.
- **Retroalimentación del esquema:** la revisión del SQL encontró tres errores en estos
  artefactos y se corrigieron aquí mismo: `EntradaBitacora.rolEjercido` sin `ADMINISTRADOR`
  (R-14, contrato), la relación `VersionPerfil.creadaPor` ausente (R-15, diagrama) y
  `umbralSilencioH` como entero (R-19, diagrama). Detalle en `revision_sql.md` §5.
- **Retroalimentación del código:** la comparación contrato-código de la Parte 2 agregó al
  contrato el `403` de cinco `GET` restringidos por rol y el `422` de `register` y de
  `PATCH /casos/{folio}` (K-5 en `revision_sql.md`).
