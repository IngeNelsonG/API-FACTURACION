// Cliente HTTP de la API. Adjunta el token, normaliza errores y, ante un 401 con
// sesión activa, borra el token y avisa a la aplicación para volver al login.

import { borrarToken, obtenerToken } from './sesion.js';

const BASE = '/api/v1';
const TIEMPO_MAXIMO_MS = 45000;
export const EVENTO_SESION_EXPIRADA = 'facturacion:sesion-expirada';

export class ErrorApi extends Error {
  constructor(estado, mensaje, { campos = [], reintentarEn = null } = {}) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.estado = estado;
    this.campos = campos;
    this.reintentarEn = reintentarEn;
  }
}

const MENSAJES = {
  0: 'No fue posible conectar con el servidor. Revise su conexión.',
  401: 'Su sesión no es válida o expiró. Inicie sesión de nuevo.',
  403: 'No tiene permisos para realizar esta acción.',
  404: 'El recurso solicitado no existe.',
  408: 'El servidor tardó demasiado en responder.',
  413: 'La información enviada es demasiado grande.',
  429: 'Demasiadas solicitudes. Intente más tarde.',
  500: 'Ocurrió un error interno. Intente de nuevo.',
  502: 'Un servicio externo no respondió correctamente.',
};

function mensajePorEstado(estado) {
  return MENSAJES[estado] || (estado >= 500 ? MENSAJES[500] : 'No fue posible completar la solicitud.');
}

async function leerError(respuesta) {
  let detalle = null;
  try {
    detalle = (await respuesta.json())?.detalle ?? null;
  } catch {
    detalle = null;
  }
  const estado = respuesta.status;
  const reintentar = Number.parseInt(respuesta.headers.get('Retry-After') || '', 10);
  const opciones = { reintentarEn: Number.isFinite(reintentar) ? reintentar : null };
  if (Array.isArray(detalle)) {
    opciones.campos = detalle
      .filter((e) => e && typeof e.mensaje === 'string')
      .map((e) => ({ campo: String(e.campo || '').replace(/^body\.?/, ''), mensaje: e.mensaje }));
    return new ErrorApi(estado, 'Revise los datos marcados.', opciones);
  }
  // Mensajes de negocio (409/422/502) del servidor son seguros para mostrar como texto.
  const usarDetalle = typeof detalle === 'string' && [409, 422].includes(estado);
  return new ErrorApi(estado, usarDetalle ? detalle : mensajePorEstado(estado), opciones);
}

/**
 * Realiza una petición. `cuerpo` puede ser un objeto (JSON) o URLSearchParams (formulario).
 * `respuesta`: 'json' | 'blob' | 'cruda'.
 */
export async function solicitar(ruta, { metodo = 'GET', cuerpo, respuesta = 'json', auth = true } = {}) {
  const cabeceras = { Accept: respuesta === 'json' ? 'application/json' : '*/*' };
  const token = auth ? obtenerToken() : null;
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  let body;
  if (cuerpo instanceof URLSearchParams) {
    body = cuerpo;
  } else if (cuerpo !== undefined) {
    cabeceras['Content-Type'] = 'application/json';
    body = JSON.stringify(cuerpo);
  }

  // Solo rutas de la propia API: impide enviar el token a otro origen ("//otro.sitio").
  if (ruta.startsWith('/') && !ruta.startsWith(`${BASE}/`)) throw new Error('Ruta no permitida');
  const url = ruta.startsWith('/') ? ruta : `${BASE}/${ruta}`;

  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), TIEMPO_MAXIMO_MS);
  let resp;
  try {
    resp = await fetch(url, {
      method: metodo,
      headers: cabeceras,
      body,
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      signal: control.signal,
    });
  } catch (error) {
    const estado = error?.name === 'AbortError' ? 408 : 0;
    throw new ErrorApi(estado, mensajePorEstado(estado));
  } finally {
    clearTimeout(temporizador);
  }

  if (!resp.ok) {
    const error = await leerError(resp);
    if (resp.status === 401 && token) {
      borrarToken();
      window.dispatchEvent(new CustomEvent(EVENTO_SESION_EXPIRADA));
    }
    throw error;
  }
  if (respuesta === 'cruda') return resp;
  if (respuesta === 'blob') return resp.blob();
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  login: (email, contrasena) =>
    solicitar('auth/login', {
      metodo: 'POST',
      auth: false,
      cuerpo: new URLSearchParams({ username: email, password: contrasena }),
    }),
  perfil: () => solicitar('auth/yo'),
  registrarUsuario: (datos) => solicitar('auth/registro', { metodo: 'POST', cuerpo: datos }),
  listarFacturas: (limite, desplazamiento) =>
    solicitar(`facturas?${new URLSearchParams({ limite: String(limite), desplazamiento: String(desplazamiento) })}`),
  obtenerFactura: (id) => solicitar(`facturas/${encodeURIComponent(id)}`),
  emitirFactura: (datos) => solicitar('facturas', { metodo: 'POST', cuerpo: datos }),
  qr: (id) => solicitar(`facturas/${encodeURIComponent(id)}/qr`, { respuesta: 'blob' }),
  enviarCorreo: (id, destinatario) =>
    solicitar(`facturas/${encodeURIComponent(id)}/correo`, {
      metodo: 'POST',
      cuerpo: destinatario ? { destinatario } : {},
    }),
  reintentarEnvio: (id) => solicitar(`facturas/${encodeURIComponent(id)}/reintentar-envio`, { metodo: 'POST' }),
  consultarEstado: (id) => solicitar(`facturas/${encodeURIComponent(id)}/consultar-estado`, { metodo: 'POST' }),
  verificacion: (cufe) => solicitar(`verificacion/${encodeURIComponent(cufe)}`, { auth: false }),
};

function nombreDeArchivo(cabecera, predeterminado) {
  const coincidencia = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cabecera || '');
  let nombre = predeterminado;
  if (coincidencia) {
    try {
      nombre = decodeURIComponent(coincidencia[1]);
    } catch {
      nombre = coincidencia[1];
    }
  }
  // Solo caracteres seguros para un nombre de archivo.
  return nombre.replace(/[^\w.-]+/g, '_').slice(0, 120) || predeterminado;
}

/** Descarga un archivo protegido: fetch con token → blob → enlace temporal → revocar. */
export async function descargar(ruta, nombrePredeterminado) {
  const resp = await solicitar(ruta, { respuesta: 'cruda' });
  const blob = await resp.blob();
  const nombre = nombreDeArchivo(resp.headers.get('Content-Disposition'), nombrePredeterminado);
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.rel = 'noopener';
  enlace.hidden = true;
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return nombre;
}
