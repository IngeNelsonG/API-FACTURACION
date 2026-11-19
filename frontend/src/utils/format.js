// Formatos para Colombia (es-CO)

/** 1250000 → "$ 1.250.000" */
export function formatCOP(value) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
}

/** SQLite guarda CURRENT_TIMESTAMP en UTC "YYYY-MM-DD HH:MM:SS" */
export function parseFechaSqlite(fecha) {
  if (!fecha) return null;
  const iso = fecha.includes('T') ? fecha : `${fecha.replace(' ', 'T')}Z`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** → "10 nov. 2026 – 10:45 a. m." en hora local (usado en Actividad reciente) */
export function formatFechaHora(fecha) {
  const d = parseFechaSqlite(fecha);
  if (!d) return '—';
  const dia = d.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
  const hora = d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit', hour12: true });
  return `${dia.replace(/ de /g, ' ')} – ${hora}`;
}

/** "carolina camargo" → "CC" ; "profe" → "PR" (usado en Sidebar y Topbar) */
export function iniciales(nombre = '') {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return '?';
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[1][0]).toUpperCase();
}

/** "profe" → "Profe" (usado en Sidebar y Dashboard) */
export const capitalizar = (texto = '') => texto.charAt(0).toUpperCase() + texto.slice(1);

/** → "28/11/2025" en hora local (usado en la tabla de Facturas) */
export function formatFecha(fecha) {
  const d = parseFechaSqlite(fecha);
  if (!d) return '—';
  return d.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric' });
}
