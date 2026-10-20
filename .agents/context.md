# Contexto

API REST de **facturación electrónica de venta** para Colombia, conectada a los servicios
web de la DIAN (validación previa, modo *Software Propio*, Anexo Técnico v1.9).

- Estado (2026-10-20): flujo completo funciona en `DIAN_MODO=simulado`; listo para
  `habilitacion` cuando se aporten certificado, SoftwareID, PIN y TestSetId. Nunca probado
  aún contra `vpfe-hab.dian.gov.co`.
- Dos modos de emisión (`FACTURACION_MODO`): `directo` (software propio) y `factus`
  (proveedor tecnológico Factus, API REST v2, sandbox; ADR-004). Factus nunca probado en vivo
  (dominio bloqueado en la nube); solo con respuestas simuladas.
- **Producción DIAN no soportada a propósito** (ADR-003). No añadir `TipoAmbiente=1`
  sin un ADR nuevo y autorización del dueño.
- Un solo emisor por despliegue, configurado por variables `EMISOR_*`.
- Funcionalidades: login JWT/Argon2id, emitir factura, descargar PDF/XML/QR, enviar por
  correo (ZIP con PDF + XML), verificación pública por CUFE (`/verificar/{cufe}` HTML,
  respaldada por `/api/v1/verificacion/{cufe}` JSON; destino del QR) e interfaz web en `/app/`.
- Guía didáctica para humanos: `docs/guia/`.
- Idioma: código, comentarios, documentación y mensajes de la API en **español**.
