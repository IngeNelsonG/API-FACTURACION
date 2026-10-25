// Utilidades de DOM y formato. Todo el contenido dinámico se inserta con textContent:
// este módulo nunca interpreta cadenas como HTML.

const SVG_NS = 'http://www.w3.org/2000/svg';

/**
 * Crea un elemento. `opciones` admite: clase, texto, atributos, datos (dataset),
 * eventos ({click: fn}), propiedades (p. ej. value, checked) e hijos.
 */
export function el(etiqueta, opciones = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  const { clase, texto, atributos, datos, eventos, propiedades } = opciones;
  if (clase) nodo.className = clase;
  if (texto !== undefined && texto !== null) nodo.textContent = String(texto);
  if (atributos) {
    for (const [nombre, valor] of Object.entries(atributos)) {
      if (valor === false || valor === null || valor === undefined) continue;
      if (/^on/i.test(nombre) || nombre === 'style') {
        throw new Error(`Atributo no permitido: ${nombre}`);
      }
      nodo.setAttribute(nombre, valor === true ? '' : String(valor));
    }
  }
  if (datos) Object.assign(nodo.dataset, datos);
  if (propiedades) Object.assign(nodo, propiedades);
  if (eventos) {
    for (const [tipo, manejador] of Object.entries(eventos)) nodo.addEventListener(tipo, manejador);
  }
  agregar(nodo, hijos);
  return nodo;
}

/** Agrega hijos (nodos o texto) ignorando valores vacíos. */
export function agregar(padre, hijos) {
  for (const hijo of hijos.flat()) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    padre.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return padre;
}

export function vaciar(nodo, ...hijos) {
  nodo.replaceChildren();
  return agregar(nodo, hijos);
}

// Íconos de trazo (24x24) construidos con createElementNS a partir de datos estáticos.
const ICONOS = {
  documento: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5', 'M9 13h6', 'M9 17h4'],
  mas: ['M12 5v14', 'M5 12h14'],
  descarga: ['M12 4v11', 'M7 10l5 5 5-5', 'M5 20h14'],
  correo: ['M4 6h16v12H4z', 'M4 7l8 6 8-6'],
  reintentar: ['M20 11a8 8 0 1 0-2.3 5.7', 'M20 5v6h-6'],
  consultar: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z', 'M20 20l-4-4'],
  externo: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'],
  copiar: ['M9 9h10v10H9z', 'M5 15V5h10'],
  basura: ['M4 7h16', 'M10 11v6', 'M14 11v6', 'M6 7l1 13h10l1-13', 'M9 7V4h6v3'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  alerta: ['M12 3l10 18H2z', 'M12 10v4', 'M12 17.5v.5'],
  cerrar: ['M6 6l12 12', 'M18 6L6 18'],
  atras: ['M15 5l-7 7 7 7'],
  usuario: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21a8 8 0 0 1 16 0'],
  vacio: ['M4 7l3-4h10l3 4', 'M4 7v13h16V7', 'M4 7h5l1 3h4l1-3h5'],
};

export function icono(nombre, clase = 'icono') {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', clase);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  for (const d of ICONOS[nombre] || []) {
    const trazo = document.createElementNS(SVG_NS, 'path');
    trazo.setAttribute('d', d);
    svg.append(trazo);
  }
  return svg;
}

// ------------------------------------------------------------------ montos (centavos)
const RE_DECIMAL = /^\d{1,13}(?:[.,]\d+)?$/;

/**
 * Convierte un decimal en texto a unidades enteras con `decimales` posiciones (BigInt),
 * sin pasar por números de coma flotante. Devuelve null si el formato no es válido
 * o si tiene más decimales de los permitidos.
 */
export function aUnidades(texto, decimales) {
  const limpio = String(texto ?? '').trim();
  if (!RE_DECIMAL.test(limpio)) return null;
  const [entera, fraccion = ''] = limpio.replace(',', '.').split('.');
  if (fraccion.length > decimales) return null;
  return BigInt(entera + fraccion.padEnd(decimales, '0'));
}

/** División entera con redondeo ROUND_HALF_UP (como el servidor) para valores ≥ 0. */
export function dividirRedondeando(numerador, divisor) {
  return (numerador * 2n + divisor) / (divisor * 2n);
}

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatearCentavos(centavos) {
  const valor = typeof centavos === 'bigint' ? centavos : BigInt(centavos);
  const negativo = valor < 0n;
  const absoluto = negativo ? -valor : valor;
  // La parte entera se formatea como BigInt; los centavos se añaden aparte (sin float).
  const entero = formatoMoneda.formatToParts(absoluto / 100n);
  const decimalesTexto = String(absoluto % 100n).padStart(2, '0');
  const partes = entero.map((parte) => (parte.type === 'fraction' ? decimalesTexto : parte.value));
  return (negativo ? '-' : '') + partes.join('');
}

/** Formatea un monto recibido de la API (texto decimal o número) como pesos colombianos. */
export function formatearMoneda(valor) {
  const centavos = aUnidades(String(valor).replace(/^-/, ''), 2);
  if (centavos === null) {
    const numero = Number(valor);
    return Number.isFinite(numero) ? formatoMoneda.format(numero) : '—';
  }
  return formatearCentavos(String(valor).startsWith('-') ? -centavos : centavos);
}

// ---------------------------------------------------------------------- fechas
const formatoFecha = new Intl.DateTimeFormat('es-CO', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
});
const formatoFechaHora = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Bogota',
});

export function formatearFecha(isoFecha) {
  if (!isoFecha) return '—';
  const fecha = new Date(`${String(isoFecha).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(fecha.getTime()) ? String(isoFecha) : formatoFecha.format(fecha);
}

export function formatearFechaHora(iso) {
  if (!iso) return '—';
  // Las fechas sin zona del servidor están en UTC.
  const texto = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const fecha = new Date(texto);
  return Number.isNaN(fecha.getTime()) ? String(iso) : formatoFechaHora.format(fecha);
}

export function hoyIso() {
  const ahora = new Date();
  const local = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------- catálogos
export const ESTADOS = {
  aceptada: { etiqueta: 'Aceptada', tono: 'exito' },
  rechazada: { etiqueta: 'Rechazada', tono: 'peligro' },
  en_proceso: { etiqueta: 'En proceso', tono: 'aviso' },
  error_envio: { etiqueta: 'Error de envío', tono: 'neutro' },
};

export const TIPOS_DOCUMENTO = [
  ['13', 'Cédula de ciudadanía'],
  ['31', 'NIT'],
  ['22', 'Cédula de extranjería'],
  ['41', 'Pasaporte'],
  ['12', 'Tarjeta de identidad'],
  ['21', 'Tarjeta de extranjería'],
  ['47', 'PEP (Permiso especial de permanencia)'],
  ['48', 'PPT (Permiso por protección temporal)'],
  ['50', 'NIT de otro país'],
  ['11', 'Registro civil'],
  ['42', 'Documento de identificación extranjero'],
];

export const MEDIOS_PAGO = [
  ['10', 'Efectivo'],
  ['42', 'Consignación bancaria'],
  ['47', 'Transferencia bancaria'],
  ['48', 'Tarjeta crédito'],
  ['49', 'Tarjeta débito'],
];

export const ROLES = { administrador: 'Administrador', facturador: 'Facturador' };

/** Solo permite URL http(s); evita esquemas como javascript: en enlaces. */
export function urlSegura(texto) {
  try {
    const url = new URL(texto, window.location.origin);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url : null;
  } catch {
    return null;
  }
}
