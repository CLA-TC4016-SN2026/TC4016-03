# Revisión de seguridad — Autenticación y protección de rutas (S05-S06-A2)

**Proyecto:** VÍNCULO — análisis de sábanas telefónicas (CDR) · **Equipo 3**
**Autor de la revisión:** Jose Benjamin Oviedo Morales (A01797548)
**Fecha:** 24 de octubre de 2026
**Código revisado:** `backend/` (FastAPI 0.141.1, PyJWT 2.15.1, bcrypt 5.0.0, psycopg 3,
PostgreSQL 18.6). Contrato: `S05_S06_A1/openapi_equipo.yaml`.

Las citas usan el formato `archivo:línea`, con rutas relativas a `backend/`. Todas las
pruebas se ejecutaron contra la API local (`http://127.0.0.1:8000`) con datos sintéticos
(dominio reservado `.example`, RFC 2606).

---

## 1. Decisiones de diseño previas a la revisión

| Decisión | Motivo |
|---|---|
| `POST /auth/register` existe, pero **solo un `ADMINISTRADOR` autenticado** puede usarlo. | En VÍNCULO las cuentas las crea el administrador técnico (supuesto S-07, vacío H-08 del SRS). Un autorregistro abierto en un sistema de procuración de justicia permitiría que cualquiera obtuviera acceso a sábanas. |
| Rol nuevo `ADMINISTRADOR`, que gestiona cuentas y **no ve casos**. | Separación de funciones: quien crea cuentas no consulta expedientes. |
| El primer administrador se crea con `scripts/crear_admin.py`, que **se niega a correr si ya existe uno**. | Resuelve el arranque sin dejar un registro abierto. La contraseña se pide con `getpass` (sin eco, fuera del historial de la shell). |
| El token lleva **un solo rol activo**, elegido al iniciar sesión. | Decisión D-2 de S04-A1: un usuario con varios roles trabaja con uno a la vez. |
| El «middleware» se implementa como **dependencias de FastAPI** (`Depends`). | Es el mecanismo idiomático de FastAPI para proteger rutas. A diferencia de un middleware ASGI global, la dependencia sabe qué ruta se pidió y qué roles admite, y queda documentada en el OpenAPI generado (candado en `/docs`). |

---

## 2. Checklist de la consigna (Parte 1)

### 2.1 ¿El JWT tiene tiempo de expiración explícito?

**Sí.** Cada token lleva `exp`, y un token sin `exp` se rechaza.

Emisión — `src/core/seguridad.py:45-50`:

```python
claims = {
    "sub": str(usuario_id),
    "rol": rol,
    "iat": ahora,
    "exp": ahora + timedelta(seconds=ajustes.jwt_expiration),
}
```

La vigencia no tiene valor por omisión en el código: sale de `JWT_EXPIRATION` y se acota entre
60 s y 24 h — `src/core/config.py:29`:

```python
jwt_expiration: int = Field(validation_alias="JWT_EXPIRATION", ge=60, le=86_400)
```

Verificación: `exp` es obligatorio — `src/core/seguridad.py:62`:

```python
options={"require": ["sub", "rol", "iat", "exp"]},
```

**Evidencia:** el token emitido por `/auth/login` decodifica como
`header={'alg': 'HS256', 'typ': 'JWT'}`, `claims=['exp', 'iat', 'rol', 'sub']`,
`exp - iat = 1800 s`. Un token firmado con el secreto correcto pero **sin `exp`** → `401`.

### 2.2 ¿`/register` devuelve la contraseña en la respuesta?

**No**, y el diseño lo impide en tres capas:

1. **Esquema de salida sin el campo.** `response_model=Usuario` (`src/api/auth.py:28`) filtra la
   respuesta, y `Usuario` no tiene contraseña ni hash — `src/schemas/auth.py:43-49`:

   ```python
   class Usuario(Esquema):
       id: UUID
       correo: EmailStr
       nombre_completo: str
       roles: list[Rol]
       activo: bool
       creado_en: datetime
   ```

2. **La consulta no lee el hash.** Las columnas públicas excluyen `contrasena_hash`
   (`src/db/usuarios.py:9`); solo `obtener_para_login` lo selecciona (`src/db/usuarios.py:35-40`).
3. **Se guarda solo el hash bcrypt**, con 12 rondas explícitas — `src/core/seguridad.py:15,25-26`:

   ```python
   def hashear_contrasena(contrasena: str) -> str:
       return bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt(_RONDAS_BCRYPT)).decode()
   ```

**Evidencia:**
- La respuesta `201` de `/auth/register` no contiene `contrasena`, `hash` ni el valor enviado
  (búsqueda automática en el cuerpo: `False`).
- En la base, todos los usuarios creados por la API tienen `contrasena_hash` con prefijo
  `$2b$12$` y 60 caracteres.
- En el contrato, `contrasena` es `writeOnly: true`.

### 2.3 ¿El middleware rechaza tokens con firma inválida o expirados?

**Sí.** `decodificar_token` verifica firma y expiración con el algoritmo **fijado**
(`src/core/seguridad.py:58-65`); cualquier `InvalidTokenError` de PyJWT se convierte en `401`
en `src/api/deps.py:38-43`:

```python
try:
    claims = decodificar_token(credenciales.credentials)
    usuario_id = UUID(claims["sub"])
    rol = Rol(claims["rol"])
except (TokenInvalido, ValueError):
    raise _NO_AUTENTICADO
```

Fijar `algorithms=[_ALGORITMO]` (`src/core/seguridad.py:13,61`) evita el ataque de confusión de
algoritmos (`alg: none`, o un token RS256 verificado como HS256).

**Evidencia** (todas contra `GET /auth/me`, todas `401` con `WWW-Authenticate: Bearer`):

| Token presentado | Resultado |
|---|---|
| Sin encabezado `Authorization` | 401 |
| Texto que no es JWT (`abc.def.ghi`) | 401 |
| Token válido con **un carácter de la firma cambiado** | 401 |
| Token **expirado** (`exp` hace 1 h), firmado con el secreto correcto | 401 |
| Token firmado con **otro secreto** | 401 |
| Token **sin `exp`** | 401 |
| Token con **`alg: none`** y sin firma | 401 |
| Token válido de una **cuenta desactivada** después de emitirlo | 401 |

El último caso se debe a un control adicional: un token bien firmado no basta; en cada petición
se comprueba que la cuenta siga activa y conserve el rol del token — `src/api/deps.py:45-48`.

### 2.4 ¿El secret del JWT está en código duro o en variable de entorno?

**En variable de entorno**, y la aplicación **no arranca** sin él — `src/core/config.py:27`:

```python
jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET", min_length=43)
```

- `SecretStr` evita que el valor aparezca en `repr()` o en logs; solo se lee con
  `get_secret_value()` al firmar y verificar (`src/core/seguridad.py:51,60`).
- Mínimo de 43 caracteres = 256 bits en base64, lo que RFC 7518 §3.2 exige para HS256.
- `src/main.py:15-16` fuerza la lectura al arrancar: la falla aparece en el despliegue, no en la
  primera petición.
- `.env.example:8` declara `JWT_SECRET=` vacío, con la instrucción `openssl rand -base64 48`, y
  `.env.example:11` declara `JWT_EXPIRATION=1800`. El `.env` real tiene permisos `600` y está
  ignorado por git (`.gitignore:19`).

**Evidencia:**
- Búsqueda en `src/` y `scripts/` de asignaciones de secretos o de tokens literales
  (`jwt_secret =`, `secret = "…"`, `eyJhbGci`): **ninguna coincidencia**.
- Arranque con `JWT_SECRET` vacío, con uno de 5 caracteres o con `JWT_EXPIRATION` vacío:
  `ValidationError` y la API no arranca.

---

## 3. Controles adicionales encontrados durante la revisión

| Control | Dónde | Prueba |
|---|---|---|
| Correo inexistente y contraseña incorrecta reciben **la misma respuesta** (RF-01-AC-3) | `src/api/auth.py:19-23,54-55` | Ambos → `401 {"detail":"Credenciales incorrectas"}`, cuerpos idénticos |
| **Mismo tiempo de respuesta** con correo inexistente: se compara contra un hash señuelo | `src/core/seguridad.py:16-18,31-38` | Evita enumerar correos midiendo tiempos |
| Pedir un rol que la cuenta no tiene → mismo `401` (no revela los roles) | `src/api/auth.py:67-68` | `rol: COORDINADOR` con cuenta de analista → 401 |
| Contraseña de 12 a **72 bytes** (límite real de bcrypt, medido en bytes UTF-8) | `src/schemas/auth.py:24,27-33` | 8 caracteres → 422; 37 «ñ» (74 bytes) → 422 |
| Correo único sin distinguir mayúsculas | índice `usuarios_correo_unico` sobre `lower(correo)` | `COORD.prueba@…` repetido → 409 |
| Campos desconocidos rechazados (`extra="forbid"`): el cliente no puede imponer `folio`, `id` o `roles` donde no corresponde | `src/schemas/base.py` | `POST /casos` con `"folio":"HACK"` → 422 |
| SQL siempre parametrizado (`%s`); nunca se concatenan valores | `src/db/usuarios.py`, `src/db/casos.py` | Revisión de código |

---

## 4. Hallazgos y correcciones propias

### H-1 · La validación 422 devolvía la contraseña en claro — **corregido**

**Hallazgo.** Durante las pruebas, `POST /auth/register` con una contraseña corta respondió:

```json
{"detail":[{"type":"string_too_short","loc":["body","contrasena"],
  "msg":"String should have at least 12 characters","input":"corta123", ...}]}
```

FastAPI repite por omisión el valor rechazado en `input`. Una contraseña mal capturada quedaba
en la respuesta HTTP, en el historial de Postman y en los logs de cualquier proxy (OWASP A09,
fallas de registro y monitoreo; CWE-209).

**Corrección.** Manejador global que elimina `input` de todos los errores de validación —
`src/main.py:25-32`:

```python
@app.exception_handler(RequestValidationError)
async def errores_de_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI repite en "input" el valor rechazado; con una contraseña la devolvería en claro.
    errores = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
```

**Verificación.** La misma petición ahora responde
`{"detail":[{"type":"string_too_short","loc":["body","contrasena"],"msg":"String should have at least 12 characters","ctx":{"min_length":12}}]}`.

### H-2 · Un `JWT_SECRET` inválido se imprimía en el log de arranque — **corregido**

**Hallazgo.** Al probar el arranque con un secreto demasiado corto, el error de Pydantic mostró
el valor: `[type=too_short, input_value='corto', input_type=str]`. Un secreto real al que le
faltara un carácter quedaría completo en `docker compose logs api`. Lo mismo aplica a
`VINCULO_DATABASE_URL`, que contiene la contraseña de PostgreSQL.

**Corrección.** `hide_input_in_errors=True` en la configuración — `src/core/config.py:19-20`.

**Verificación.** El mismo arranque ahora muestra
`Value should have at least 43 items after validation, not 18 [type=too_short]`, sin el valor. Una
búsqueda del secreto y de la contraseña de prueba en la salida: 0 coincidencias.

### H-3 · El script de *seed* habría descartado al administrador — **corregido antes de usarlo**

**Hallazgo.** La primera versión de `scripts/crear_admin.py` obtenía la conexión con el generador
`get_db()` y lo cerraba con `.close()`. Eso lanza `GeneratorExit` dentro del bloque
`with psycopg.connect(...)`, y psycopg lo trata como un error: **rollback**. El script habría
informado «Administrador creado» sin guardar nada.

**Corrección.** Usar `get_connection()` directamente, que hace commit al salir del `with` sin
excepción (`scripts/crear_admin.py`).

### H-4 · Autorregistro abierto (riesgo de la consigna) — **mitigado por diseño**

La consigna describe `/auth/register` abierto. En VÍNCULO eso permitiría que cualquier persona
se diera de alta con el rol que eligiera. Se restringió al `ADMINISTRADOR` —
`src/api/auth.py:30`:

```python
dependencies=[Depends(requiere_roles(Rol.ADMINISTRADOR))],
```

**Verificación:** `register` sin token → 401; con token de `ANALISTA` → 403; con token de
`ADMINISTRADOR` → 201.

---

## 5. Riesgos que quedan abiertos

Se declaran para no dar por resuelto lo que no lo está.

| Riesgo | Situación | Siguiente paso propuesto |
|---|---|---|
| **Sin bloqueo por intentos fallidos ni limitación de tasa** en `/auth/login` | RNF-15 pide bloquear la cuenta 15 min tras 5 intentos; no está implementado | Contador de intentos en `usuarios` o límite por IP en nginx (`limit_req`) |
| **Sin revocación de tokens** | Un token robado vale hasta su `exp` (30 min). Desactivar la cuenta sí lo invalida (§2.3) | `DELETE /sesiones/actual` del contrato S04 con lista de `jti` revocados |
| **`/docs` y `/openapi.json` públicos** | Describen toda la API sin autenticación | Desactivarlos en la VM (`docs_url=None`) o protegerlos en nginx; **decisión del alumno** |
| **Secreto simétrico (HS256)** | Quien tenga `JWT_SECRET` puede emitir tokens. Hoy solo la API lo usa | Rotación del secreto; RS256 si otro servicio necesita verificar tokens |
| **HTTP sin TLS** | Local y en la VM todo va por `127.0.0.1` o túnel SSH | TLS en nginx antes de exponer a la red |
| **Un `POST /casos` rechazado consume un folio** | La secuencia de PostgreSQL no se revierte | Aceptable; documentado (no hay huecos «sospechosos» que ocultar) |

---

## 6. Protección de rutas (Parte 2)

### 6.1 Mecanismo

`src/api/deps.py` define las dos dependencias:

- `usuario_actual` (`src/api/deps.py:31-49`): exige `Authorization: Bearer <token>` válido → si
  no, **401** con `WWW-Authenticate: Bearer`.
- `requiere_roles(*permitidos)` (`src/api/deps.py:55-61`): depende de `usuario_actual` y además
  exige que el rol activo esté permitido → si no, **403**:

  ```python
  def requiere_roles(*permitidos: Rol) -> Callable[[UsuarioActual], UsuarioActual]:
      def verificar(usuario: UsuarioAutenticado) -> UsuarioActual:
          if usuario.rol_activo not in permitidos:
              raise _PERMISO_INSUFICIENTE
          return usuario
  ```

Se aplican por ruta en `src/api/casos.py:22-23`:

```python
_LECTURA = [Depends(requiere_roles(Rol.COORDINADOR, Rol.ANALISTA, Rol.MP_PERITO))]
_ESCRITURA = [Depends(requiere_roles(Rol.COORDINADOR))]
```

### 6.2 Rutas protegidas y nivel de acceso

Todas las operaciones del contrato heredan `security: [BearerAuth: []]` (seguridad global) salvo
las dos que declaran `security: []`. Los roles salen de `x-roles` de `openapi_equipo.yaml`.

| Método | Ruta | BearerAuth | Roles permitidos | Otros roles | Código |
|---|---|---|---|---|---|
| GET | `/health` | No | — | — | `src/api/health.py` |
| POST | `/auth/login` | No | — | — | `src/api/auth.py:47` |
| POST | `/auth/register` | **Sí** | `ADMINISTRADOR` | 403 | `src/api/auth.py:26-31` |
| GET | `/auth/me` | **Sí** | Los cinco roles | — | `src/api/auth.py:74-76` |
| GET | `/casos` | **Sí** | `COORDINADOR`, `ANALISTA`, `MP_PERITO` | 403 | `src/api/casos.py:32` |
| POST | `/casos` | **Sí** | `COORDINADOR` | 403 | `src/api/casos.py:37-39` |
| GET | `/casos/{folio}` | **Sí** | `COORDINADOR`, `ANALISTA`, `MP_PERITO` | 403 | `src/api/casos.py:49` |
| PUT | `/casos/{folio}` | **Sí** | `COORDINADOR` | 403 | `src/api/casos.py:57` |
| DELETE | `/casos/{folio}` | **Sí** | `COORDINADOR` | 403 | `src/api/casos.py:68-70` |

`ADMINISTRADOR` y `AUDITOR` no tienen acceso a casos (separación de funciones; RNF-04 para el
auditor).

### 6.3 Verificación automática: código contra contrato

Un script recorrió el árbol de dependencias de cada ruta registrada en FastAPI, extrajo si exige
`usuario_actual` y qué roles admite, y lo comparó con `security` y `x-roles` del contrato:

```
Rutas en el código: 9 · operaciones en el contrato: 9 · discrepancias: 0
```

Así se confirma que **ninguna** ruta marcada con `BearerAuth` quedó sin la dependencia.

### 6.4 Pruebas manuales desde la terminal

Ejecutadas el 24/10/2026 con `curl` contra `http://127.0.0.1:8000`. Los tokens se obtuvieron con
`POST /auth/login` de cuentas sintéticas (`coord.prueba@vinculo.example`, rol `COORDINADOR`;
`analista.prueba@vinculo.example`, rol `ANALISTA`), creadas con `POST /auth/register` y un token
de administrador y borradas al terminar. El token «alterado» es el del coordinador con el primer
carácter de la firma cambiado.

Ejemplo de las peticiones:

```bash
# Sin token
curl -i -X POST http://127.0.0.1:8000/casos -H 'Content-Type: application/json' \
     -d '{"numeroSolicitud":"S-200","mpSolicitanteId":"<uuid del MP>"}'

# Con token
curl -i -X POST http://127.0.0.1:8000/casos -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"numeroSolicitud":"S-200","mpSolicitanteId":"<uuid del MP>"}'
```

| # | Caso de la consigna | Petición | Esperado | Obtenido | Cuerpo |
|---|---|---|---|---|---|
| 1 | Token válido y rol correcto | `POST /casos` (coordinador) | 201 | **201** ✓ | `{"folio":"C-000003","numeroSolicitud":"S-200","estado":"ABIERTO",…}` |
| 2 | Sin token | `POST /casos` | 401 | **401** ✓ | `{"detail":"No autenticado"}` |
| 3 | Sin token | `GET /casos` | 401 | **401** ✓ | `{"detail":"No autenticado"}` |
| 4 | Token inválido (1 carácter) | `GET /casos` | 401 | **401** ✓ | `{"detail":"No autenticado"}` |
| 5 | Token inválido (1 carácter) | `POST /casos` | 401 | **401** ✓ | `{"detail":"No autenticado"}` |
| 6 | Rol incorrecto | `POST /casos` (analista) | 403 | **403** ✓ | `{"detail":"Permiso insuficiente"}` |
| 7 | Rol incorrecto | `PUT /casos/C-000003` (analista) | 403 | **403** ✓ | `{"detail":"Permiso insuficiente"}` |
| 8 | Rol incorrecto | `DELETE /casos/C-000003` (analista) | 403 | **403** ✓ | `{"detail":"Permiso insuficiente"}` |
| 9 | Rol incorrecto | `GET /casos` (administrador) | 403 | **403** ✓ | `{"detail":"Permiso insuficiente"}` |
| 10 | Token válido y rol correcto | `GET /casos` (analista) | 200 | **200** ✓ | `[{"folio":"C-000003",…}]` |
| 11 | Token válido y rol correcto | `GET /casos/C-000003` (analista) | 200 | **200** ✓ | `{"folio":"C-000003",…}` |
| 12 | Token válido y rol correcto | `PUT /casos/C-000003` (coordinador) | 200 | **200** ✓ | `{…,"numeroSolicitud":"S-200-B",…}` |
| 13 | Sin token **y** cuerpo inválido | `POST /casos` con `{"x":1}` | 401 | **401** ✓ | `{"detail":"No autenticado"}` |
| 14 | Token válido y rol correcto | `DELETE /casos/C-000003` (coordinador) | 204 | **204** ✓ | (sin cuerpo) |

**Resultado: 14 de 14 casos con el código esperado.**

La prueba 13 confirma que la autenticación se evalúa **antes** que la validación del cuerpo: sin
token no se obtienen mensajes 422 que revelen el esquema de la API.
