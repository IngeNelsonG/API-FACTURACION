# Guía: pasar de modo simulado a habilitación DIAN

Hoy la API funciona completa en `DIAN_MODO=simulado`. Para el detalle de cómo obtener cada dato, vea [paso-a-paso-credenciales.md](paso-a-paso-credenciales.md). Para conectarla al ambiente
de **habilitación** (pruebas) de la DIAN necesita aportar:

| Dato | Variable | Dónde se obtiene |
|---|---|---|
| Certificado de firma digital `.p12`/`.pfx` | `DIAN_CERTIFICADO_RUTA` (ej. `certificados/firma.p12`) | Entidad acreditada ONAC (Certicámara, GSE, Andes SCD…) |
| Clave del certificado | `DIAN_CERTIFICADO_CLAVE` | La entrega la certificadora |
| SoftwareID | `DIAN_SOFTWARE_ID` | Portal DIAN → Habilitación → Software propio |
| PIN del software | `DIAN_PIN` | Lo define usted al registrar el software |
| TestSetId | `DIAN_TEST_SET_ID` | Portal de habilitación, al registrar el software |
| Rango de pruebas y clave técnica | `NUMERACION_*` | Portal de habilitación (por defecto `SETP` 990000000–995000000) |
| Datos del emisor idénticos al RUT | `EMISOR_*` | RUT |
| Servidor SMTP (para correo real) | `CORREO_MODO=smtp`, `SMTP_*` | Su proveedor de correo |

El certificado va en `certificados/` (ignorado por git) y las claves solo en `.env`
o en el gestor de secretos del despliegue. **Nunca** se versionan.

## Pasos

1. Complete las variables anteriores en `.env` y ponga `DIAN_MODO=habilitacion`.
   Si falta algo, la API no arranca y lista las variables faltantes.
2. Emita las facturas del set de pruebas (`POST /api/v1/facturas`). Con
   `DIAN_TEST_SET_ID` definido se envían con `SendTestSetAsync` y quedan `en_proceso`.
3. Consulte cada una con `POST /api/v1/facturas/{id}/consultar-estado` hasta que
   queden `aceptada` o `rechazada` (revise `respuesta_dian.mensajes`).
4. Cuando el portal muestre el set como aceptado, el software queda **Habilitado**.
   Vacíe `DIAN_TEST_SET_ID` para usar `SendBillSync`.
5. Producción no está soportada (ver [ADR-003](../decisions/ADR-003-integracion-dian.md)).

## Pendiente de validar contra la DIAN real

- Nada se ha probado aún contra `vpfe-hab.dian.gov.co`: la firma XAdES y WS-Security
  se verificaron criptográficamente de forma local, no con el validador de la DIAN.
- Validar el XML contra los XSD oficiales del Anexo 1.9 (guardar en `recursos/xsd/`).
- La cadena TLS de la DIAN usa el almacén de CA de `certifi`.
- El correo al adquiriente adjunta el XML firmado y el `ApplicationResponse` por
  separado; el anexo pide un `AttachedDocument` (pendiente).
- Notas crédito/débito (CUDE) y eventos RADIAN no están implementados.
