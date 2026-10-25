// Gestión de usuarios (solo administradores): creación de cuentas.

import { api } from './api.js';
import { esAdministrador } from './auth.js';
import { boton, campo, conCarga, encabezadoPagina, estadoVacio, marcarError, notificar } from './ui.js';
import { el, ROLES } from './utils.js';

const MIN_CLAVE = 12;
const MAX_CLAVE = 128;
const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validarClave(clave) {
  if (clave.length < MIN_CLAVE || clave.length > MAX_CLAVE) return `Debe tener entre ${MIN_CLAVE} y ${MAX_CLAVE} caracteres.`;
  if (clave.trim() !== clave) return 'No puede empezar ni terminar con espacios.';
  if (new Set(clave).size < 4) return 'Es demasiado débil: use caracteres más variados.';
  return '';
}

export function renderizarUsuarios(principal) {
  if (!esAdministrador()) {
    principal.replaceChildren(
      estadoVacio({ titulo: 'Acceso restringido', texto: 'Solo los administradores pueden gestionar usuarios.', iconoNombre: 'alerta' }),
    );
    return;
  }

  const c = {
    email: campo({ etiqueta: 'Correo electrónico', nombre: 'email', tipo: 'email', requerido: true, atributos: { maxlength: '254', autocomplete: 'off', spellcheck: 'false' } }),
    nombre: campo({ etiqueta: 'Nombre', nombre: 'nombre', requerido: true, atributos: { maxlength: '120', autocomplete: 'off' } }),
    contrasena: campo({
      etiqueta: 'Contraseña',
      nombre: 'contrasena',
      tipo: 'password',
      requerido: true,
      ayuda: `Entre ${MIN_CLAVE} y ${MAX_CLAVE} caracteres. Se recomienda una frase larga y única.`,
      atributos: { minlength: String(MIN_CLAVE), maxlength: String(MAX_CLAVE), autocomplete: 'new-password' },
    }),
    confirmacion: campo({ etiqueta: 'Confirmar contraseña', nombre: 'confirmacion', tipo: 'password', requerido: true, atributos: { maxlength: String(MAX_CLAVE), autocomplete: 'new-password' } }),
    rol: campo({ etiqueta: 'Rol', nombre: 'rol', control: 'select', opciones: Object.entries(ROLES).reverse(), valor: 'facturador' }),
  };
  const crear = boton('Crear usuario', { tipo: 'submit', icono: 'usuario' });
  const creados = el('ul', { clase: 'lista-usuarios' });
  const tarjetaCreados = el(
    'section',
    { clase: 'tarjeta', atributos: { hidden: true } },
    el('h2', { clase: 'tarjeta__titulo', texto: 'Creados en esta sesión' }),
    creados,
  );

  const formulario = el(
    'form',
    { clase: 'tarjeta seccion', atributos: { novalidate: true, 'aria-label': 'Crear usuario' } },
    el('h2', { clase: 'tarjeta__titulo', texto: 'Nuevo usuario' }),
    el('div', { clase: 'rejilla' }, c.email.raiz, c.nombre.raiz, c.contrasena.raiz, c.confirmacion.raiz, c.rol.raiz),
    el(
      'p',
      { clase: 'texto-secundario' },
      'Los facturadores solo ven sus propias facturas. Los administradores ven todas y pueden crear usuarios.',
    ),
    el('div', { clase: 'seccion__pie' }, crear),
  );

  formulario.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const email = c.email.control.value.trim();
    const nombre = c.nombre.control.value.trim();
    const clave = c.contrasena.control.value;
    const errores = [];
    if (!RE_EMAIL.test(email) || !c.email.control.checkValidity()) errores.push([c.email, 'Ingrese un correo electrónico válido.']);
    if (!nombre) errores.push([c.nombre, 'Ingrese el nombre.']);
    const problemaClave = validarClave(clave);
    if (problemaClave) errores.push([c.contrasena, problemaClave]);
    if (clave !== c.confirmacion.control.value) errores.push([c.confirmacion, 'Las contraseñas no coinciden.']);
    for (const [control, mensaje] of errores) marcarError(control, mensaje);
    if (errores.length) {
      errores[0][0].control.focus();
      return;
    }
    try {
      const usuario = await conCarga(
        crear,
        () => api.registrarUsuario({ email, nombre, contrasena: clave, rol: c.rol.control.value }),
        'Creando…',
      );
      notificar(`Usuario ${usuario.email} creado.`);
      formulario.reset();
      c.rol.control.value = 'facturador';
      creados.prepend(
        el(
          'li',
          { clase: 'lista-usuarios__elemento' },
          el('div', { clase: 'celda-doble' }, el('span', { clase: 'celda-doble__principal', texto: usuario.nombre }), el('span', { clase: 'celda-doble__secundario', texto: usuario.email })),
          el('span', { clase: 'etiqueta-rol', texto: ROLES[usuario.rol] || usuario.rol }),
          el('span', { clase: 'texto-secundario', texto: usuario.activo ? 'Activo' : 'Inactivo' }),
        ),
      );
      tarjetaCreados.hidden = false;
      c.email.control.focus();
    } catch (error) {
      if (error.estado === 401) return;
      c.contrasena.control.value = '';
      c.confirmacion.control.value = '';
      if (error.estado === 409) marcarError(c.email, error.message);
      else if (error.estado === 422 && !error.campos.length) marcarError(c.contrasena, error.message);
      else if (error.campos.length) {
        for (const { campo: nombreCampo, mensaje } of error.campos) if (c[nombreCampo]) marcarError(c[nombreCampo], mensaje);
      }
      notificar(error.message, 'error');
    }
  });

  principal.replaceChildren(
    encabezadoPagina('Usuarios', { subtitulo: 'Cree cuentas para las personas que emiten facturas.' }),
    el('div', { clase: 'columna-estrecha' }, formulario, tarjetaCreados),
  );
  c.email.control.focus();
}
