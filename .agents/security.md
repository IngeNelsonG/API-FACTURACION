# Reglas de seguridad (obligatorias)

- Nunca versionar secretos: `.env`, `certificados/*`, `*.p12`, `*.pem` están ignorados. Usar `.env.example`.
- Secretos en `SecretStr`; nunca registrarlos en logs ni devolverlos en respuestas.
- Todo XML externo con parser seguro (`resolve_entities=False, no_network=True`).
- TLS siempre verificado (httpx, SMTP con `ssl.create_default_context()`).
- Consultas solo con SQLAlchemy parametrizado; filtrar por dueño (IDOR) salvo administrador.
- El rol se lee de la BD, no del JWT. JWT HS256 con `iss/aud/exp/nbf/iat/jti/sub` obligatorios.
- Texto de usuario escapado antes de reportlab `Paragraph`; CR/LF prohibidos en cabeceras de correo.
- La verificación pública no expone datos del adquiriente.
- Errores 500 sin detalles; 422 sin eco del valor recibido.
- Modelo de amenazas: `docs/security/modelo-de-amenazas.md`.
