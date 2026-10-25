// Punto de entrada de la SPA: enrutamiento por hash, barra superior y control de sesión.

import { EVENTO_SESION_EXPIRADA } from './api.js';
import { cargarPerfil, cerrarSesion, esAdministrador, haySesion, usuario } from './auth.js';
import { estadoVacio, notificar } from './ui.js';
import { el, ROLES } from './utils.js';
import { renderizarDetalle } from './vista-detalle.js';
import { renderizarFacturas } from './vista-facturas.js';
import { renderizarLogin } from './vista-login.js';
import { renderizarNuevaFactura } from './vista-nueva.js';
import { renderizarUsuarios } from './vista-usuarios.js';

const NOMBRE_APP = 'Facturación Electrónica';
const RE_ID = /^[A-Za-z0-9_-]{1,64}$/;

const principal = document.getElementById('principal');
const barra = document.getElementById('barra');
let limpiezaActual = null;
let numeroNavegacion = 0;
let sesionVisible = false;

function resolverRuta() {
  const [ruta, consulta = ''] = window.location.hash.replace(/^#/, '').split('?');
  const partes = ruta.split('/').filter(Boolean);
  const params = new URLSearchParams(consulta);
  if (partes.length === 0 || (partes.length === 1 && partes[0] === 'facturas')) {
    return { nombre: 'facturas', titulo: 'Facturas', vista: (p, ctx) => renderizarFacturas(p, { ...ctx, consulta: params }) };
  }
  if (partes[0] === 'facturas' && partes.length === 2 && partes[1] === 'nueva') {
    return { nombre: 'nueva', titulo: 'Nueva factura', vista: renderizarNuevaFactura };
  }
  if (partes[0] === 'facturas' && partes.length === 2 && RE_ID.test(partes[1])) {
    return { nombre: 'facturas', titulo: 'Detalle de factura', vista: (p, ctx) => renderizarDetalle(p, { ...ctx, id: partes[1] }) };
  }
  if (partes.length === 1 && partes[0] === 'usuarios') {
    return { nombre: 'usuarios', titulo: 'Usuarios', vista: renderizarUsuarios };
  }
  return {
    nombre: '',
    titulo: 'Página no encontrada',
    vista: (p) =>
      p.replaceChildren(
        estadoVacio({
          titulo: 'Página no encontrada',
          texto: 'La dirección no corresponde a ninguna sección.',
          iconoNombre: 'alerta',
          accion: el('a', { clase: 'boton boton--primario', atributos: { href: '#/facturas' } }, el('span', { clase: 'boton__texto', texto: 'Ir a facturas' })),
        }),
      ),
  };
}

export function navegar(hash) {
  if (window.location.hash === hash) enrutar();
  else window.location.hash = hash;
}

function pintarBarra(nombreRuta) {
  const actual = usuario();
  barra.hidden = false;
  document.getElementById('usuario-nombre').textContent = actual?.nombre || '';
  document.getElementById('usuario-rol').textContent = ROLES[actual?.rol] || actual?.rol || '';
  document.getElementById('enlace-usuarios').hidden = !esAdministrador();
  for (const enlace of barra.querySelectorAll('[data-ruta]')) {
    if (enlace.dataset.ruta === nombreRuta) enlace.setAttribute('aria-current', 'page');
    else enlace.removeAttribute('aria-current');
  }
}

function mostrarLogin() {
  sesionVisible = false;
  barra.hidden = true;
  document.title = `Iniciar sesión · ${NOMBRE_APP}`;
  renderizarLogin(principal, {
    alIniciar: () => {
      if (!window.location.hash || window.location.hash === '#/') window.location.hash = '#/facturas';
      enrutar();
    },
  });
}

async function enrutar() {
  const numero = ++numeroNavegacion;
  if (limpiezaActual) {
    limpiezaActual();
    limpiezaActual = null;
  }
  for (const dialogo of document.querySelectorAll('dialog[open]')) dialogo.close();

  if (!haySesion()) {
    mostrarLogin();
    return;
  }
  if (!usuario()) {
    try {
      await cargarPerfil();
    } catch (error) {
      if (error.estado !== 401) {
        principal.replaceChildren(estadoVacio({ titulo: 'Sin conexión con la API', texto: error.message, iconoNombre: 'alerta' }));
      }
      return;
    }
    if (numero !== numeroNavegacion) return;
  }

  sesionVisible = true;
  const ruta = resolverRuta();
  pintarBarra(ruta.nombre);
  document.title = `${ruta.titulo} · ${NOMBRE_APP}`;
  window.scrollTo(0, 0);
  const resultado = await ruta.vista(principal, { navegar });
  if (typeof resultado === 'function') {
    // Si el usuario navegó mientras la vista cargaba, se limpia de inmediato.
    if (numero === numeroNavegacion) limpiezaActual = resultado;
    else resultado();
  }
  if (numero === numeroNavegacion && !principal.contains(document.activeElement)) {
    principal.querySelector('h1')?.focus({ preventScroll: true });
  }
}

document.getElementById('boton-salir').addEventListener('click', () => {
  cerrarSesion();
  notificar('Sesión cerrada.', 'info', 3000);
  enrutar();
});

window.addEventListener(EVENTO_SESION_EXPIRADA, () => {
  const estabaDentro = sesionVisible;
  cerrarSesion();
  // Varias peticiones pueden fallar a la vez: solo se reacciona a la primera.
  if (!estabaDentro && principal.querySelector('.login')) return;
  if (estabaDentro) notificar('Su sesión expiró. Inicie sesión de nuevo.', 'error');
  enrutar();
});

window.addEventListener('hashchange', enrutar);
enrutar();
