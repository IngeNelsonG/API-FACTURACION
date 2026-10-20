// Componentes de interfaz reutilizables: toasts, insignias, botones con carga,
// campos de formulario accesibles, diálogos y estados vacíos.

import { ESTADOS, el, icono } from './utils.js';

// ---------------------------------------------------------------------- toasts
export function notificar(mensaje, tipo = 'exito', duracionMs = 5000) {
  const contenedor = document.getElementById('toasts');
  if (!contenedor) return;
  const cerrar = () => {
    toast.classList.add('toast--saliendo');
    setTimeout(() => toast.remove(), 200);
  };
  const toast = el(
    'div',
    { clase: `toast toast--${tipo}`, atributos: { role: tipo === 'error' ? 'alert' : 'status' } },
    icono(tipo === 'error' ? 'alerta' : 'check', 'icono toast__icono'),
    el('p', { clase: 'toast__texto', texto: mensaje }),
    el(
      'button',
      {
        clase: 'toast__cerrar',
        atributos: { type: 'button', 'aria-label': 'Cerrar notificación' },
        eventos: { click: cerrar },
      },
      icono('cerrar'),
    ),
  );
  contenedor.append(toast);
  if (duracionMs > 0) setTimeout(cerrar, tipo === 'error' ? duracionMs * 1.6 : duracionMs);
}

// ---------------------------------------------------------------------- insignias
export function insigniaEstado(estado) {
  const info = ESTADOS[estado] || { etiqueta: String(estado || 'Desconocido'), tono: 'neutro' };
  return el(
    'span',
    { clase: `insignia insignia--${info.tono}` },
    el('span', { clase: 'insignia__punto', atributos: { 'aria-hidden': 'true' } }),
    info.etiqueta,
  );
}

// ---------------------------------------------------------------------- botones
export function boton(texto, { variante = 'primario', icono: nombreIcono, tipo = 'button', alPulsar, atributos = {}, clase = '' } = {}) {
  return el(
    'button',
    {
      clase: `boton boton--${variante} ${clase}`.trim(),
      atributos: { type: tipo, ...atributos },
      eventos: alPulsar ? { click: alPulsar } : undefined,
    },
    nombreIcono ? icono(nombreIcono) : null,
    el('span', { clase: 'boton__texto', texto }),
  );
}

/** Ejecuta `tarea` mostrando el botón en estado de carga; evita dobles envíos. */
export async function conCarga(botonNodo, tarea, textoCarga) {
  if (botonNodo.getAttribute('aria-busy') === 'true') return undefined;
  const textoNodo = botonNodo.querySelector('.boton__texto');
  const original = textoNodo ? textoNodo.textContent : null;
  botonNodo.setAttribute('aria-busy', 'true');
  botonNodo.disabled = true;
  if (textoNodo && textoCarga) textoNodo.textContent = textoCarga;
  try {
    return await tarea();
  } finally {
    botonNodo.removeAttribute('aria-busy');
    botonNodo.disabled = false;
    if (textoNodo && original !== null) textoNodo.textContent = original;
  }
}

// ---------------------------------------------------------------------- campos
let contadorCampos = 0;

/**
 * Crea un campo con etiqueta, ayuda y mensaje de error enlazados por aria-describedby.
 * `control` puede ser 'input' | 'select' | 'textarea'. Devuelve {raiz, control, error}.
 */
export function campo({ etiqueta, nombre, control = 'input', tipo = 'text', requerido = false, ayuda, opciones, atributos = {}, valor, clase = '' }) {
  contadorCampos += 1;
  const id = `campo-${nombre.replace(/[^\w-]/g, '-')}-${contadorCampos}`;
  const idError = `${id}-error`;
  const idAyuda = `${id}-ayuda`;
  const describe = [ayuda ? idAyuda : null, idError].filter(Boolean).join(' ');
  const attrs = { id, name: nombre, 'aria-describedby': describe, ...atributos };
  if (requerido) attrs['aria-required'] = 'true';
  if (control === 'input') attrs.type = tipo;

  const nodo = el(control, { clase: `control control--${control}`, atributos: attrs });
  if (control === 'select' && opciones) {
    for (const [codigo, texto] of opciones) nodo.append(el('option', { texto, atributos: { value: codigo } }));
  }
  if (valor !== undefined) nodo.value = valor;

  const error = el('p', { clase: 'campo__error', atributos: { id: idError } });
  const raiz = el(
    'div',
    { clase: `campo ${clase}`.trim(), datos: { campo: nombre } },
    el(
      'label',
      { clase: 'campo__etiqueta', atributos: { for: id } },
      etiqueta,
      requerido ? el('span', { clase: 'campo__requerido', texto: ' *', atributos: { 'aria-hidden': 'true' } }) : null,
    ),
    nodo,
    ayuda ? el('p', { clase: 'campo__ayuda', texto: ayuda, atributos: { id: idAyuda } }) : null,
    error,
  );
  nodo.addEventListener('input', () => marcarError({ control: nodo, error }, ''));
  return { raiz, control: nodo, error };
}

export function marcarError({ control, error }, mensaje) {
  error.textContent = mensaje || '';
  if (mensaje) control.setAttribute('aria-invalid', 'true');
  else control.removeAttribute('aria-invalid');
}

// ---------------------------------------------------------------------- diálogos
/**
 * Abre un <dialog> modal (gestiona foco y Escape de forma nativa).
 * `construir(cerrar)` devuelve el contenido. Resuelve con el valor pasado a `cerrar`.
 */
export function abrirDialogo({ titulo, construir }) {
  return new Promise((resolver) => {
    const idTitulo = `dialogo-titulo-${Date.now()}`;
    const dialogo = el('dialog', { clase: 'dialogo', atributos: { 'aria-labelledby': idTitulo } });
    let resultado = null;
    const cerrar = (valor = null) => {
      resultado = valor;
      dialogo.close();
    };
    dialogo.addEventListener('close', () => {
      dialogo.remove();
      resolver(resultado);
    });
    dialogo.append(
      el(
        'div',
        { clase: 'dialogo__cabecera' },
        el('h2', { clase: 'dialogo__titulo', texto: titulo, atributos: { id: idTitulo } }),
        el(
          'button',
          {
            clase: 'boton-icono',
            atributos: { type: 'button', 'aria-label': 'Cerrar' },
            eventos: { click: () => cerrar(null) },
          },
          icono('cerrar'),
        ),
      ),
      construir(cerrar),
    );
    document.body.append(dialogo);
    dialogo.showModal();
  });
}

// ---------------------------------------------------------------------- estados
export function estadoVacio({ titulo, texto, accion, iconoNombre = 'vacio' }) {
  return el(
    'div',
    { clase: 'vacio' },
    el('div', { clase: 'vacio__icono' }, icono(iconoNombre)),
    el('h2', { clase: 'vacio__titulo', texto: titulo }),
    texto ? el('p', { clase: 'vacio__texto', texto }) : null,
    accion || null,
  );
}

export function cargando(texto = 'Cargando…') {
  return el(
    'div',
    { clase: 'cargando', atributos: { role: 'status' } },
    el('span', { clase: 'girador', atributos: { 'aria-hidden': 'true' } }),
    el('span', { texto }),
  );
}

export function encabezadoPagina(titulo, { subtitulo, acciones = [], volver } = {}) {
  return el(
    'div',
    { clase: 'encabezado' },
    el(
      'div',
      { clase: 'encabezado__textos' },
      volver
        ? el('a', { clase: 'enlace-volver', atributos: { href: volver.href } }, icono('atras'), volver.texto)
        : null,
      el('h1', { clase: 'encabezado__titulo', texto: titulo, atributos: { tabindex: '-1' } }),
      subtitulo ? el('p', { clase: 'encabezado__subtitulo' }, subtitulo) : null,
    ),
    acciones.length ? el('div', { clase: 'encabezado__acciones' }, acciones) : null,
  );
}
