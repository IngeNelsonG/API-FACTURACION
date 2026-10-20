// Autenticación: login (OAuth2 password flow), perfil del usuario y cierre de sesión.

import { api, ErrorApi } from './api.js';
import { borrarToken, guardarToken, obtenerToken } from './sesion.js';

let usuarioActual = null;

export function usuario() {
  return usuarioActual;
}

export function esAdministrador() {
  return usuarioActual?.rol === 'administrador';
}

export function haySesion() {
  return Boolean(obtenerToken());
}

export async function iniciarSesion(email, contrasena) {
  const respuesta = await api.login(email.trim(), contrasena);
  if (!respuesta?.access_token) throw new ErrorApi(500, 'Respuesta de autenticación inválida.');
  guardarToken(respuesta.access_token);
  return cargarPerfil();
}

export async function cargarPerfil() {
  usuarioActual = await api.perfil();
  return usuarioActual;
}

export function cerrarSesion() {
  usuarioActual = null;
  borrarToken();
}

/** Mensaje genérico para el login: no revela si el correo existe. */
export function mensajeLogin(error) {
  if (!(error instanceof ErrorApi)) return 'No fue posible iniciar sesión.';
  if (error.estado === 401 || error.estado === 422) return 'Correo o contraseña incorrectos.';
  if (error.estado === 429) {
    const minutos = error.reintentarEn ? Math.max(1, Math.ceil(error.reintentarEn / 60)) : null;
    return minutos
      ? `Demasiados intentos fallidos. Intente de nuevo en ${minutos} ${minutos === 1 ? 'minuto' : 'minutos'}.`
      : 'Demasiados intentos fallidos. Intente más tarde.';
  }
  return error.message;
}
