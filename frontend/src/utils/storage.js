// Persistencia de la sesión en localStorage (envuelto en try/catch por modo incógnito, etc.)
const SESSION_KEY = 'facturapro_session';

export function saveSession(session) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* sin almacenamiento disponible: la sesión vive solo en memoria */
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    // El back devuelve "expira" en ISO; si ya venció, se descarta
    if (!session?.token || new Date(session.expira) <= new Date()) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* nada que limpiar */
  }
}
