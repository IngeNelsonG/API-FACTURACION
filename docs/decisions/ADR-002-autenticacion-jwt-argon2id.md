# ADR-002: Autenticación con JWT y contraseñas con Argon2id

## Status

Accepted

## Context

Se pidió un login con JWT usando bcrypt o Argon. La API la consumen otros sistemas o
un frontend, sin sesiones de navegador.

## Decision

- **Argon2id** (`argon2-cffi`, parámetros RFC 9106 "low memory": t=3, m=64 MiB, p=4)
  para el hash de contraseñas, con rehash transparente si cambian los parámetros.
- **JWT HS256** de acceso, vida corta (30 min por defecto), con `iss`, `aud`, `exp`,
  `nbf`, `iat`, `jti` y `sub` obligatorios y lista fija de algoritmos.
- Flujo **OAuth2 password** (`POST /api/v1/auth/login`, formulario) para que Swagger UI funcione.
- El **rol se lee de la base de datos** en cada petición, no del token.
- Roles: `administrador` (crea usuarios, ve todas las facturas) y `facturador`
  (solo sus facturas). El primer administrador se crea por CLI.
- Limitador de intentos por IP+correo (5 en 5 min por defecto) y mensaje de error único.

## Alternatives Considered

- **bcrypt**: sólido, pero trunca a 72 bytes y no es resistente a memoria; Argon2id es la
  primera recomendación de OWASP.
- **RS256/EdDSA**: útil si otros servicios validan tokens; con un solo servicio, HS256
  con un secreto fuerte es más simple. Migrable cambiando `seguridad/tokens.py`.
- **Refresh tokens**: no incluidos aún (ver `.agents/tasks/pendientes.md`).

## Consequences

- Revocar un token antes de que expire requiere desactivar al usuario (efecto inmediato)
  o rotar `JWT_SECRETO` (invalida todos).
- Cada login cuesta ~64 MiB de RAM durante el hash: el limitador y el límite de
  longitud (128) evitan abuso.

## Security Considerations

- `JWT_SECRETO` ≥ 32 caracteres; en producción se rechaza el valor por defecto.
- El usuario inexistente también ejecuta una verificación Argon2 (señuelo) para no filtrar
  qué correos existen por tiempo de respuesta.
- El limitador es en memoria por proceso: con varias réplicas debe pasar a Redis.

## Date

2026-10-19
