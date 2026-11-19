import { http } from './httpClient';

/**
 * POST /login  →  { mensaje, token, usuario, rol, expira }
 * El back espera exactamente las llaves "usuario" y "clave".
 */
export function login(usuario, clave) {
  return http('/login', {
    method: 'POST',
    body: { usuario, clave },
    auth: false,
  });
}

/**
 * POST /registro → crea la cuenta y registra a la persona como cliente.
 * datos: { usuario, clave, nombre, cedula, rut, direccion, correo, telefono }
 */
export function registrar(datos) {
  return http('/registro', { method: 'POST', body: datos, auth: false });
}
