import { loadSession, clearSession } from '@/utils/storage';

/**
 * - En desarrollo (npm run dev): "/api", que Vite reenvía a Flask (ver vite.config.js).
 * - En producción (npm run build): VITE_API_URL, p. ej. la URL de la API en la nube.
 */
export const API_URL = import.meta.env.DEV ? '/api' : import.meta.env.VITE_API_URL || '/api';

/** Error con el status HTTP para poder reaccionar distinto a 400 / 401 / 500 */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Cliente HTTP único de la app.
 * - Agrega "Authorization: Bearer <token>" si hay sesión (lo que espera @token_required).
 * - Convierte los { "error": "..." } del back en ApiError.
 */
export async function http(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };

  if (auth) {
    const session = loadSession();
    if (session?.token) headers.Authorization = `Bearer ${session.token}`;
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('No se pudo conectar con el servidor. ¿Está corriendo la API?', 0);
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    // Token vencido o inválido en una ruta protegida → cerrar sesión local
    if (response.status === 401 && auth) clearSession();
    throw new ApiError(data.error || 'Ocurrió un error inesperado', response.status);
  }

  return data;
}
