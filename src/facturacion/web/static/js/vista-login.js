// Pantalla de inicio de sesión.

import { iniciarSesion, mensajeLogin } from './auth.js';
import { boton, campo, conCarga, marcarError } from './ui.js';
import { el } from './utils.js';

export function renderizarLogin(principal, { alIniciar }) {
  const email = campo({
    etiqueta: 'Correo electrónico',
    nombre: 'username',
    tipo: 'email',
    requerido: true,
    atributos: { autocomplete: 'username', maxlength: '254', inputmode: 'email', spellcheck: 'false' },
  });
  const clave = campo({
    etiqueta: 'Contraseña',
    nombre: 'password',
    tipo: 'password',
    requerido: true,
    atributos: { autocomplete: 'current-password', maxlength: '128' },
  });
  const alerta = el('div', { clase: 'alerta alerta--error', atributos: { role: 'alert', hidden: true } });
  const enviar = boton('Iniciar sesión', { tipo: 'submit', clase: 'boton--bloque' });

  const formulario = el(
    'form',
    { clase: 'formulario-login', atributos: { novalidate: true, 'aria-labelledby': 'titulo-login' } },
    alerta,
    email.raiz,
    clave.raiz,
    enviar,
  );

  formulario.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    alerta.hidden = true;
    const correo = email.control.value.trim();
    let valido = true;
    if (!correo || !email.control.checkValidity()) {
      marcarError(email, 'Ingrese un correo electrónico válido.');
      valido = false;
    }
    if (!clave.control.value) {
      marcarError(clave, 'Ingrese su contraseña.');
      valido = false;
    }
    if (!valido) {
      formulario.querySelector('[aria-invalid="true"]')?.focus();
      return;
    }
    try {
      await conCarga(enviar, () => iniciarSesion(correo, clave.control.value), 'Ingresando…');
      clave.control.value = '';
      alIniciar();
    } catch (error) {
      clave.control.value = '';
      alerta.textContent = mensajeLogin(error);
      alerta.hidden = false;
      clave.control.focus();
    }
  });

  principal.replaceChildren(
    el(
      'section',
      { clase: 'login' },
      el(
        'div',
        { clase: 'tarjeta login__tarjeta' },
        el(
          'div',
          { clase: 'login__cabecera' },
          el('img', { clase: 'marca__logo marca__logo--grande', atributos: { src: '/app/img/logo.svg', alt: '', width: '48', height: '48' } }),
          el('h1', { clase: 'login__titulo', texto: 'Facturación Electrónica', atributos: { id: 'titulo-login' } }),
          el('p', { clase: 'login__subtitulo', texto: 'Inicie sesión para emitir y consultar sus facturas.' }),
        ),
        formulario,
      ),
      el('p', { clase: 'login__pie', texto: 'Conexión directa con los servicios web de la DIAN · Ambiente de habilitación' }),
    ),
  );
  email.control.focus();
}
