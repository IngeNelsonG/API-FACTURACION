# 6. Preguntas probables en la sustentación

> Respuestas modelo, cortas y con el archivo que las respalda. Úselas como guion, no para
> memorizar: lo que convence es poder abrir el código y mostrarlo.

## Diseño y tecnología

**1. ¿Por qué Python y FastAPI?**
FastAPI valida la entrada con Pydantic (tipos, patrones, `extra="forbid"`) y genera OpenAPI/
Swagger solo. Python tiene buenas librerías para lo difícil del dominio: `lxml` (XML seguro),
`signxml` (XAdES), `cryptography`, `reportlab` (PDF), `segno` (QR). Java con DSS tiene el XAdES
más maduro, pero es mucho más pesado para un proyecto de este tamaño
([ADR-001](../decisions/ADR-001-stack-tecnologico.md)).

**2. ¿Qué arquitectura usó y por qué?**
Monolito modular con puertos y adaptadores (hexagonal). El dominio (`dominio/`, `ubl/`) no
depende de FastAPI ni de la BD; DIAN, firma, correo y proveedor son `Protocol` con adaptador
real y simulado; `arranque.py` los elige según la configuración. Beneficios: pruebas sin red,
y cambiar de simulado a habilitación o a Factus es solo configuración. Microservicios no se
justifican con un solo emisor.

**3. ¿Por qué un cliente SOAP propio y no `zeep`?**
La DIAN exige WS-Security firmando solo `wsa:To`, con un formato muy específico. `zeep` firma el
`Body` por defecto y necesita `xmlsec` (dependencia nativa). Construir el sobre en
`dian/soap.py:construir_sobre` es una función pura, fácil de probar.

**4. ¿Por qué `Decimal` y no `float`?**
`0.1 + 0.2 != 0.3` en binario. El mismo valor debe aparecer idéntico en el XML y en la cadena
del CUFE; un centavo de diferencia es un rechazo. Todo usa `Decimal` con `ROUND_HALF_UP` a 2
decimales (`dominio/factura.py:redondear`). Hasta el JS de la interfaz calcula con `BigInt`.

## Facturación electrónica

**5. ¿Cómo se calcula el CUFE?**
SHA-384 de la concatenación sin separadores de: número, fecha, hora con `-05:00`, subtotal,
`01`+IVA, `04`+INC, `03`+ICA, total, NIT del emisor, documento del adquiriente, clave técnica y
tipo de ambiente (`dominio/cufe.py:cadena_cufe`). Se verificó con el ejemplo del Anexo Técnico
(`tests/unitarias/test_dominio.py::test_cufe_coincide_con_el_ejemplo_del_anexo_tecnico`).

**6. ¿Para qué sirve la firma XAdES si ya está el CUFE?**
El CUFE identifica y amarra los valores principales, pero lo puede recalcular quien conozca la
clave técnica. La firma con la llave privada del certificado prueba **quién** emitió el documento
y que **ningún byte** cambió (integridad y no repudio). EPES agrega la política de firma DIAN v2.

**7. ¿Cómo garantiza la numeración consecutiva sin duplicados ni huecos?**
`persistencia/repositorios.py:siguiente_consecutivo` hace `UPDATE consecutivos SET valor = valor
+ 1 … RETURNING valor`: incremento y lectura atómicos; la BD serializa a los concurrentes. Se
ejecuta en la misma transacción que guarda la factura: si algo falla antes del `commit`, el
`rollback` devuelve el número. Ese `commit` se hace antes de llamar a la DIAN, para no
mantener el bloqueo de la fila durante la llamada de red. Además `facturas.numero` y `facturas.cufe` son `UNIQUE`. El
único caso en que se "gasta" un número es cuando la DIAN no responde: la factura queda guardada
en `error_envio` y se reintenta con el mismo número.

**8. ¿Qué pasa si la DIAN está caída?**
Modo directo: `ClienteDianSoap` convierte timeouts/errores HTTP en `ErrorDian`; el servicio guarda
la factura en `error_envio` con el XML ya firmado (se guardó **antes** de llamar a la DIAN), y
`POST /api/v1/facturas/{id}/reintentar-envio` la reenvía. Modo Factus: antes de llamar se guarda un
registro pendiente con la `referencia`; si Factus no responde queda `error_envio` para conciliar
y la API responde 502 (aquí no se permite reenviar, para no duplicar). Pendiente: reintentos
programados y consultar `GetStatus` por CUFE antes de reenviar.

**9. ¿Por qué el modo simulado es legítimo y no "hacer trampa"?**
Porque simula **solo la frontera externa**: todo lo demás es real (XML UBL, CUFE, firma XAdES
verificable criptográficamente, ZIP, persistencia, PDF, QR). El simulador (`dian/simulado.py`)
incluso valida que el ZIP tenga un único XML bien formado, firmado y con CUFE válido, y
rechaza si no. Es el mismo principio de los *test doubles*. Además se declara siempre: el PDF
dice "SIN VALIDEZ TRIBUTARIA" y el `ApplicationResponse` simulado lo indica en una nota.

**10. ¿Qué diferencia hay entre su modo directo y el modo Factus?**
En directo la API numera, calcula el CUFE, firma y habla SOAP con la DIAN. En Factus envía los
datos de negocio por REST (OAuth2) y Factus hace eso; la API sigue validando, calculando
totales, guardando, generando PDF/QR, enviando correo y verificando. Ver la tabla de la
[guía 2](02-recorrido-del-codigo.md#25-la-misma-petición-en-modo-factus).

**11. ¿Qué tiene el QR y a dónde lleva?**
Número, fecha, hora, NIT, documento del adquiriente, valores, CUFE y una URL
(`dominio/cufe.py:contenido_qr`). Por defecto la URL es `/verificar/{cufe}`, una página pública
que consulta `GET /api/v1/verificacion/{cufe}` y muestra solo datos del emisor y del documento.
Con `QR_URL_MODO=dian` o en modo Factus apunta al catálogo de la DIAN.

**12. ¿Por qué no soporta producción?**
Decisión explícita ([ADR-003](../decisions/ADR-003-integracion-dian.md)): emitir con validez
tributaria por error tendría consecuencias legales. `tipo_ambiente_dian` devuelve siempre `"2"`;
activar producción exige un ADR nuevo.

## Seguridad

**13. ¿Por qué Argon2id y no bcrypt?**
Argon2id ganó la Password Hashing Competition y es la primera recomendación de OWASP: usa
memoria (64 MiB por hash), lo que encarece los ataques con GPU/ASIC; bcrypt usa ~4 KiB y trunca
a 72 bytes. Se usa `argon2-cffi` con parámetros RFC 9106 y rehash automático
(`seguridad/contrasenas.py`).

**14. ¿Cómo valida el JWT y qué evita?**
HS256 con lista fija de algoritmos (bloquea `alg: none` y confusión RS/HS) y reclamos
obligatorios `exp, iat, nbf, iss, aud, sub, jti` (`seguridad/tokens.py:validar_token`). El rol
se lee de la BD en cada petición, así que manipular el token no da privilegios y desactivar un
usuario es inmediato.

**15. ¿Cómo evita que un usuario vea facturas de otro?**
Filtrando por dueño en la consulta SQL (`api/rutas/facturas.py:_cargar` →
`repositorios.obtener_factura`) y respondiendo 404, no 403. Los ids son UUID4. Hay un test para
esto.

**16. ¿Cómo protege la interfaz web contra XSS?**
Nunca usa `innerHTML`: todo se construye con `createElement`/`textContent` (`js/utils.js:el`),
un test lo verifica, y la CSP `script-src 'self'` sin `unsafe-inline` bloquea scripts
inyectados. El token va en `sessionStorage` y las peticiones solo pueden ir a `/api/v1/`.

**17. ¿Qué riesgos de seguridad quedan?**
Limitador en memoria (no sirve con varias réplicas), sin revocación de JWT, sin cifrado en
reposo de datos personales, TLS dependiente del proxy, logs no estructurados y que un
reintento tras *timeout* puede chocar con un documento que la DIAN ya procesó. Lista completa en la
[guía 3](03-seguridad-explicada.md#314-riesgos-residuales-conocidos).

## Operación y futuro

**18. ¿Cómo lo escalaría?**
La API es casi sin estado: se pueden correr varias réplicas detrás de un balanceador con
PostgreSQL gestionado. Antes hay que (1) mover el limitador de login a Redis, (2) asegurar que
el consecutivo siga en la BD (ya lo está) y (3) sacar el envío a la DIAN y el correo a una cola
(Celery/RQ, SQS) con reintentos, para no bloquear la petición HTTP. En la nube: contenedor (el
`Dockerfile` ya corre sin root) en Cloud Run/ECS/App Service, secretos en un gestor
(Secret Manager, Key Vault) y el certificado `.p12` montado como secreto.

**19. ¿Qué cambiaría para producción?**
Nuevo ADR y `TipoAmbiente=1` con endpoints `vpfe.dian.gov.co`; certificado ONAC real; resolución
de numeración real; validar el XML contra los XSD oficiales; notas crédito/débito (CUDE) y
`AttachedDocument`; reintentos programados; Redis; logs JSON y monitoreo
(OpenTelemetry/Sentry); copias de seguridad y cifrado en reposo; TLS en el proxy y
`ENTORNO=produccion` (que ya desactiva Swagger, exige secreto propio y envía HSTS).

**20. ¿Cómo sabe que funciona? ¿Qué pruebas tiene?**
Más de 180 pruebas con `pytest` (`tests/unitarias/` sin BD ni red; `tests/integracion/` con
`TestClient` y SQLite temporal), cobertura mínima de 85 % exigida en CI, `ruff` con reglas de
seguridad, `pip-audit` y verificación de que las migraciones aplican y revierten
(`.github/workflows/ci.yml`). La firma XAdES se verifica criptográficamente en las pruebas.

**21. ¿Lo probó contra la DIAN o Factus reales?**
No, y es importante decirlo. La DIAN requiere credenciales de habilitación que no se tienen, y
el entorno de desarrollo en la nube bloqueaba el dominio de Factus. Ambas integraciones se
construyeron según la documentación oficial y se probaron con transportes simulados
(`httpx.MockTransport`). Es el siguiente paso de la hoja de ruta
([guía 5](05-factus-sandbox.md#58-qué-está-verificado-y-qué-no)).

**22. ¿Qué haría distinto si empezara de nuevo?**
Respuesta honesta posible: agregar desde el inicio una cola de trabajos para la transmisión,
un *lockfile* con hashes de dependencias y logs estructurados; y descargar primero los XSD del
anexo para validar el XML en las pruebas.
