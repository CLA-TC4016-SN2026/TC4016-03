# Arquitectura del Equipo 3 — VÍNCULO (S05-S06-A1)

**Equipo 3:** Francisco Leonardo Armendáriz Cavazos, José Francisco González Vargas, José Benjamín
Oviedo Morales y Mario Sánchez Valtierra.
**Base:** `S04_A1/decision_arquitectonica.md` y `S04_A1/diagrama_componentes.puml` de J. B. Oviedo,
adoptados por acuerdo del equipo el 2026-10-24. Los cambios respecto de esa base (A-1 a A-3) se
justifican en `diferencias_diseno.md`.
**Contrato:** `openapi_equipo.yaml`. **Modelo:** `diagrama_clases_equipo.puml`.

## Decisión (se mantiene ADR-001 de S04-A1)

Cliente-servidor con **backend monolítico modular en capas** y un proceso *worker* para las
cargas, con la cola de trabajos en la misma base PostgreSQL. Los motivos de S04 siguen vigentes:
un solo desarrollador por módulo, 8 sesiones simultáneas (RNF-14), consultas analíticas cerca de
los datos (RNF-07) y cargas de hasta 5 minutos que no deben bloquear la API (RNF-08).

| Elemento | Tecnología | Estado al cierre de S05-S06 |
|---|---|---|
| Aplicación web (SPA) | React 19, TypeScript | Construida (esqueleto); las vistas de análisis son de S07-S08 |
| Servidor web | nginx sin privilegios, `:8080`; quita el prefijo `/api` | Construido |
| API REST | Python 3.13, FastAPI 0.141, Pydantic 2, psycopg 3 | Construida: autenticación, usuarios, casos, líneas, asignaciones y perfiles |
| Base de datos | PostgreSQL 18 + PostGIS | Construida; esquema en `esquema_bd.sql` |
| Worker de carga | Misma imagen que la API | Planeado (S07 en adelante) |
| Almacén de originales | Volumen de solo-agregar | Planeado |

## Cambios respecto de S04-A1

- **A-1 · Capa de servicios.** S04 define routers → servicios → repositorios. La A2 llamaba del
  router al repositorio. Desde esta actividad los routers solo traducen HTTP y delegan en
  servicios (`backend/src/services/`), que aplican las reglas de negocio; los repositorios
  (`backend/src/db/`) solo ejecutan SQL parametrizado. Los `Protocol` de repositorio que pide el
  principio D se agregan con las pruebas de S09, cuando haya un segundo implementador (dobles de
  prueba).
- **A-2 · Worker y almacén siguen planeados.** Ninguna operación de esta etapa encola trabajos.
- **A-3 · Autenticación sin estado.** S04 modelaba una `Sesion` guardada en el servidor. Se usa
  un JWT HS256 con el rol activo como *claim* y vigencia de `JWT_EXPIRATION`; en cada petición la
  API relee la cuenta, de modo que desactivarla o retirarle el rol invalida el token. La expiración
  por inactividad (RNF-15) queda como deuda.

## Vista de contenedores (C4 nivel 2)

![Contenedores](imagenes/arquitectura_contenedores.png)

```plantuml
@startuml arquitectura_contenedores
!include <C4/C4_Container>

LAYOUT_TOP_DOWN()
AddElementTag("planeado", $bgColor="#8FA3B8", $borderStyle=DashedLine(), $legendText="Diseñado, aún no construido")
AddRelTag("planeado", $lineStyle=DashedLine(), $legendText="Interfaz diseñada, aún no construida")

title VÍNCULO — Contenedores (C4 nivel 2), consolidado del Equipo 3
caption Construidos al cierre de S05-S06: SPA, servidor web, API y base de datos. TLS pendiente.

Person(admin, "Administrador técnico", "Crea cuentas; no ve casos (S-07)")
Person(coordinador, "Coordinador", "Crea, asigna, cierra y revisa casos")
Person(analista, "Analista", "Carga, depura y analiza las sábanas de sus casos")
Person(mp, "MP / Perito", "Consulta hallazgos y exporta dictámenes")
Person(auditor, "Auditor", "Consulta y verifica la bitácora; no ve eventos (RNF-04)")

System_Boundary(vinculo, "VÍNCULO — red interna de la unidad, sin internet (RNF-12)") {
  Container(spa, "Aplicación web", "React 19, TypeScript", "Vistas por rol; mapa de áreas, nunca puntos (RD-02)")
  Container(web, "Servidor web", "nginx (:8080)", "Sirve la SPA; reenvía /api/* a la API sin el prefijo")
  Container(api, "API REST", "Python 3.13, FastAPI, Pydantic, psycopg 3", "JWT con rol activo; casos, líneas, asignaciones, perfiles; errores RFC 9457")
  Container(worker, "Worker de carga", "Python 3.13, misma imagen", "Ejecuta la carga completa en una transacción (RNF-08, RNF-10)", $tags="planeado")
  ContainerDb(db, "Base de datos", "PostgreSQL 18 + PostGIS", "Usuarios, casos, perfiles, eventos, bitácora y cola de trabajos")
  ContainerDb(originales, "Almacén de originales", "Volumen de solo-agregar", "Original de cada oficio, base del SHA-256 (RF-03)", $tags="planeado")
}

Rel(admin, spa, "Usa")
Rel(coordinador, spa, "Usa")
Rel(analista, spa, "Usa")
Rel(mp, spa, "Usa")
Rel(auditor, spa, "Usa")
Rel(spa, web, "Descarga la SPA; llama a /api/*", "HTTP (TLS pendiente)")
Rel(web, api, "Reenvía /api/* sin el prefijo", "HTTP/JSON, red interna de Docker")
Rel(api, db, "Lee y escribe", "SQL parametrizado, psycopg 3")
Rel(api, originales, "Guarda el original", "Sistema de archivos", $tags="planeado")
Rel(worker, db, "Toma trabajos (FOR UPDATE SKIP LOCKED)", "SQL", $tags="planeado")
Rel(worker, originales, "Lee el original", "Sistema de archivos", $tags="planeado")

SHOW_LEGEND()
@enduml
```

## Vista de componentes de la API (C4 nivel 3)

![Componentes](imagenes/arquitectura_componentes.png)

```plantuml
@startuml arquitectura_componentes
!include <C4/C4_Component>

LAYOUT_TOP_DOWN()
AddElementTag("planeado", $bgColor="#8FA3B8", $borderStyle=DashedLine(), $legendText="Diseñado, aún no construido")
AddElementTag("patron", $bgColor="#3E6A8F", $fontColor="#FFFFFF", $legendText="Implementa un patrón (ADR-002)")
AddRelTag("planeado", $lineStyle=DashedLine(), $legendText="Interfaz diseñada, aún no construida")

title VÍNCULO — Componentes de la API (C4 nivel 3), consolidado del Equipo 3

Container(spa, "Aplicación web", "React 19", "Consume openapi_equipo.yaml")
ContainerDb(db, "Base de datos", "PostgreSQL 18 + PostGIS")

Container_Boundary(apiB, "API REST (FastAPI)") {
  Component(routers, "Routers", "FastAPI APIRouter (src/api)", "Delgados: validan con Pydantic y delegan. auth, usuarios, casos, perfiles, health")
  Component(errores, "Errores RFC 9457", "Manejadores globales (src/main.py)", "application/problem+json; 400 esquema, 422 dominio; nunca repite el valor rechazado")
  Component(authn, "Autenticación", "bcrypt + PyJWT HS256 (src/core/seguridad.py)", "Hash de contraseñas y emisión/verificación del token con rol activo")
  Component(authz, "Autorización", "Dependencias de FastAPI (src/api/deps.py)", "usuario_actual (401) y requiere_roles (403); relee la cuenta en cada petición")
  Component(svcCasos, "Servicio de casos", "Python (src/services/casos.py)", "Alta con líneas, cierre, líneas objetivo, asignaciones; visibilidad por asignación (RNF-02)")
  Component(svcPerfiles, "Servicio de perfiles", "Python (src/services/perfiles.py)", "Perfiles de concesionario versionados (RF-29)")
  Component(svcIngesta, "Servicio de ingesta", "Python", "Original, hash y encolado (RF-03, RF-04)", $tags="planeado")
  Component(svcAnalisis, "Servicio de análisis", "Estrategia: ProductoAnalisis", "Productos RF-07 a RF-14", $tags="planeado")
  Component(svcDictamen, "Servicio de dictámenes", "Python", "Compone, exporta y verifica (RF-19)", $tags="planeado")
  Component(bitacora, "Bitácora", "Observador síncrono", "Entrada encadenada en la misma transacción (RF-21, RNF-05)", $tags="planeado")
  Component(repos, "Repositorios", "Repositorio, psycopg 3 (src/db)", "Un módulo por agregado; SQL parametrizado; una transacción por petición", $tags="patron")
}

Rel(spa, routers, "REST/JSON vía nginx")
Rel(routers, authz, "Depende de")
Rel(authz, authn, "Verifica el token")
Rel(routers, errores, "Excepciones")
Rel(routers, svcCasos, "Delega")
Rel(routers, svcPerfiles, "Delega")
Rel(routers, svcIngesta, "Delega", $tags="planeado")
Rel(routers, svcAnalisis, "Delega", $tags="planeado")
Rel(routers, svcDictamen, "Delega", $tags="planeado")
Rel(svcCasos, repos, "Usa")
Rel(svcPerfiles, repos, "Usa")
Rel(authz, repos, "Relee la cuenta")
Rel(svcCasos, bitacora, "Publica", $tags="planeado")
Rel(repos, db, "SQL")

SHOW_LEGEND()
@enduml
```

## Principios que se conservan

- **Reglas de dominio en el modelo:** RD-01 (metadatos, nunca contenido), RD-02/RD-04 (la radiobase
  es zona de cobertura, nunca un punto) y RD-03 (el sistema no concluye).
- **SOLID y DRY:** una sola dependencia de autorización para todos los routers; servicios con una
  responsabilidad cada uno.
- **KISS:** cola en PostgreSQL en lugar de un broker; JWT sin estado en lugar de sesiones en base.
