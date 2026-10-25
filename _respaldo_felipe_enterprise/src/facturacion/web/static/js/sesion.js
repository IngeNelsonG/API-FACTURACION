// Almacenamiento del token de acceso: en memoria y en sessionStorage (se borra al cerrar
// la pestaña). Nunca en localStorage ni en cookies accesibles desde JS.

const CLAVE = 'facturacion.token';
let tokenEnMemoria = null;

function almacen() {
  try {
    return window.sessionStorage;
  } catch {
    return null; // Almacenamiento bloqueado: se usa solo la memoria.
  }
}

export function obtenerToken() {
  if (tokenEnMemoria) return tokenEnMemoria;
  try {
    tokenEnMemoria = almacen()?.getItem(CLAVE) || null;
  } catch {
    tokenEnMemoria = null;
  }
  return tokenEnMemoria;
}

export function guardarToken(token) {
  tokenEnMemoria = token;
  try {
    almacen()?.setItem(CLAVE, token);
  } catch {
    // Sin almacenamiento la sesión dura lo que dure la página.
  }
}

export function borrarToken() {
  tokenEnMemoria = null;
  try {
    almacen()?.removeItem(CLAVE);
  } catch {
    // Nada que borrar.
  }
}
