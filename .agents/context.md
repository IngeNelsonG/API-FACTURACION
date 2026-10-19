# Contexto

API REST de **facturación electrónica de venta** para Colombia, conectada a los servicios
web de la DIAN (validación previa, modo *Software Propio*, Anexo Técnico v1.9).

- Estado (2026-10-19): flujo completo funciona en `DIAN_MODO=simulado`; listo para
  `habilitacion` cuando se aporten certificado, SoftwareID, PIN y TestSetId. Nunca probado
  aún contra `vpfe-hab.dian.gov.co`.
- **Producción DIAN no soportada a propósito** (ADR-003). No añadir `TipoAmbiente=1`
  sin un ADR nuevo y autorización del dueño.
- Un solo emisor por despliegue, configurado por variables `EMISOR_*`.
- Funcionalidades: login JWT/Argon2id, emitir factura, descargar PDF/XML/QR, enviar por
  correo (ZIP con PDF + XML), verificación pública por CUFE (destino del QR).
- Idioma: código, comentarios, documentación y mensajes de la API en **español**.
