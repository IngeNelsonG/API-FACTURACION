// Detalle de una factura: datos, respuesta de la DIAN, QR y acciones.

import { api, descargar } from './api.js';
import {
  abrirDialogo,
  boton,
  campo,
  cargando,
  conCarga,
  encabezadoPagina,
  estadoVacio,
  insigniaEstado,
  marcarError,
  notificar,
} from './ui.js';
import { el, formatearFecha, formatearFechaHora, formatearMoneda, icono, urlSegura } from './utils.js';

const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function dato(etiqueta, valor, clase = '') {
  return el(
    'div',
    { clase: `datos__fila ${clase}`.trim() },
    el('dt', { texto: etiqueta }),
    el('dd', {}, valor === null || valor === undefined || valor === '' ? '—' : valor),
  );
}

function tarjeta(titulo, ...contenido) {
  return el('section', { clase: 'tarjeta' }, el('h2', { clase: 'tarjeta__titulo', texto: titulo }), ...contenido);
}

/**
 * Enlace a la página de verificación. Si la API apunta al JSON público de este mismo
 * servidor, se usa la página legible /verificar/{cufe}.
 */
function urlVerificacion(factura) {
  const url = urlSegura(factura.url_verificacion);
  if (!url) return null;
  if (url.origin === window.location.origin && url.pathname.startsWith('/api/v1/verificacion/')) {
    return new URL(`/verificar/${encodeURIComponent(factura.cufe)}`, window.location.origin);
  }
  return url;
}

async function dialogoCorreo(factura) {
  return abrirDialogo({
    titulo: 'Enviar factura por correo',
    construir: (cerrar) => {
      const destinatario = campo({
        etiqueta: 'Destinatario (opcional)',
        nombre: 'destinatario',
        tipo: 'email',
        ayuda: `Si lo deja vacío se enviará a ${factura.adquiriente_email}.`,
        atributos: { maxlength: '254', autocomplete: 'email', placeholder: factura.adquiriente_email, spellcheck: 'false' },
      });
      const enviar = boton('Enviar', { tipo: 'submit', icono: 'correo' });
      const formulario = el(
        'form',
        { clase: 'dialogo__cuerpo', atributos: { novalidate: true, method: 'dialog' } },
        el('p', { clase: 'texto-secundario', texto: 'Se enviará un ZIP con el PDF y el XML firmado de la factura.' }),
        destinatario.raiz,
        el(
          'div',
          { clase: 'dialogo__acciones' },
          boton('Cancelar', { variante: 'fantasma', alPulsar: () => cerrar(null) }),
          enviar,
        ),
      );
      formulario.addEventListener('submit', async (evento) => {
        evento.preventDefault();
        const correo = destinatario.control.value.trim();
        if (correo && !(RE_EMAIL.test(correo) && destinatario.control.checkValidity())) {
          marcarError(destinatario, 'Ingrese un correo electrónico válido.');
          destinatario.control.focus();
          return;
        }
        try {
          const respuesta = await conCarga(enviar, () => api.enviarCorreo(factura.id, correo || null), 'Enviando…');
          cerrar(respuesta);
        } catch (error) {
          if (error.estado === 401) {
            cerrar(null);
            return;
          }
          if (error.campos?.length) marcarError(destinatario, 'Ingrese un correo electrónico válido.');
          else notificar(error.message, 'error');
        }
      });
      queueMicrotask(() => destinatario.control.focus());
      return formulario;
    },
  });
}

export async function renderizarDetalle(principal, { id }) {
  let activo = true;
  let urlQr = null;
  const imagenQr = el('img', { clase: 'qr__imagen', atributos: { alt: 'Código QR de la factura', width: '220', height: '220', hidden: true } });
  const marcadorQr = el('div', { clase: 'qr__marcador' }, cargando('Generando QR…'));

  principal.replaceChildren(cargando('Cargando factura…'));

  const limpiar = () => {
    activo = false;
    if (urlQr) URL.revokeObjectURL(urlQr);
    urlQr = null;
  };

  async function cargarQr() {
    try {
      const blob = await api.qr(id);
      if (!activo) return;
      urlQr = URL.createObjectURL(blob);
      imagenQr.src = urlQr;
      imagenQr.hidden = false;
      marcadorQr.remove();
    } catch (error) {
      if (activo && error.estado !== 401) marcadorQr.replaceChildren(el('p', { clase: 'texto-secundario', texto: 'No fue posible cargar el QR.' }));
    }
  }

  function pintar(factura) {
    if (!activo) return;
    imagenQr.alt = `Código QR de la factura ${factura.numero}`;
    const acciones = [];
    const accionDescarga = (texto, ruta, extension) =>
      boton(texto, {
        variante: 'secundario',
        icono: 'descarga',
        alPulsar: async (evento) => {
          const nodo = evento.currentTarget;
          try {
            await conCarga(nodo, () => descargar(ruta, `${factura.numero}.${extension}`), 'Descargando…');
          } catch (error) {
            if (error.estado !== 401) notificar(error.message, 'error');
          }
        },
      });
    acciones.push(accionDescarga('PDF', factura.enlaces.pdf, 'pdf'), accionDescarga('XML', factura.enlaces.xml, 'xml'));

    const correo = boton('Enviar por correo', {
      variante: 'secundario',
      icono: 'correo',
      alPulsar: async () => {
        const respuesta = await dialogoCorreo(factura);
        if (respuesta?.enviado_a) {
          notificar(`Factura enviada a ${respuesta.enviado_a}.`);
          recargar();
        }
      },
    });
    if (factura.estado !== 'aceptada') {
      correo.disabled = true;
      correo.title = 'Solo se pueden enviar facturas aceptadas por la DIAN';
    }
    acciones.push(correo);

    const accionEstado = (texto, nombreIcono, tarea, exito) =>
      boton(texto, {
        icono: nombreIcono,
        alPulsar: async (evento) => {
          try {
            const actualizada = await conCarga(evento.currentTarget, tarea, 'Procesando…');
            notificar(exito(actualizada), actualizada.estado === 'aceptada' ? 'exito' : 'info');
            pintar(actualizada);
          } catch (error) {
            if (error.estado !== 401) notificar(error.message, 'error');
          }
        },
      });
    if (factura.estado === 'error_envio') {
      acciones.push(accionEstado('Reintentar envío', 'reintentar', () => api.reintentarEnvio(factura.id), (f) => `Reenvío realizado: ${f.estado.replace('_', ' ')}.`));
    }
    if (factura.estado === 'en_proceso' && factura.track_id) {
      acciones.push(accionEstado('Consultar estado', 'consultar', () => api.consultarEstado(factura.id), (f) => `Estado actual: ${f.estado.replace('_', ' ')}.`));
    }

    const respuesta = factura.respuesta_dian || {};
    const mensajes = Array.isArray(respuesta.mensajes) ? respuesta.mensajes : [];
    const verificacion = urlVerificacion(factura);

    const copiar = el(
      'button',
      { clase: 'boton-icono', atributos: { type: 'button', 'aria-label': 'Copiar CUFE', title: 'Copiar CUFE' } },
      icono('copiar'),
    );
    copiar.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(factura.cufe);
        notificar('CUFE copiado al portapapeles.', 'info', 2500);
      } catch {
        notificar('No fue posible copiar el CUFE.', 'error');
      }
    });

    principal.replaceChildren(
      encabezadoPagina(`Factura ${factura.numero}`, {
        subtitulo: [insigniaEstado(factura.estado), el('span', { texto: factura.adquiriente_nombre })],
        volver: { href: '#/facturas', texto: 'Facturas' },
        acciones,
      }),
      el(
        'div',
        { clase: 'detalle' },
        el(
          'div',
          { clase: 'detalle__principal' },
          tarjeta(
            'Datos de la factura',
            el('p', { clase: 'total-destacado numero', texto: formatearMoneda(factura.total) }),
            el(
              'dl',
              { clase: 'datos' },
              dato('Número', factura.numero),
              dato('Fecha de emisión', formatearFecha(factura.fecha_emision)),
              dato('Estado', insigniaEstado(factura.estado)),
              dato('Registrada', formatearFechaHora(factura.creado_en)),
              dato('Track ID', factura.track_id ? el('code', { clase: 'codigo', texto: factura.track_id }) : null),
              dato('Correo enviado', factura.correo_enviado_en ? formatearFechaHora(factura.correo_enviado_en) : 'No enviado'),
            ),
          ),
          tarjeta(
            'Adquiriente',
            el(
              'dl',
              { clase: 'datos' },
              dato('Nombre', factura.adquiriente_nombre),
              dato('Documento', factura.adquiriente_documento),
              dato('Correo', factura.adquiriente_email),
            ),
          ),
          tarjeta(
            'Respuesta de la DIAN',
            el(
              'dl',
              { clase: 'datos' },
              dato('Código', respuesta.codigo ? el('code', { clase: 'codigo', texto: respuesta.codigo }) : null),
              dato('Descripción', respuesta.descripcion),
            ),
            mensajes.length
              ? el('ul', { clase: 'mensajes-dian' }, mensajes.map((m) => el('li', { texto: m })))
              : el('p', { clase: 'texto-secundario', texto: 'Sin mensajes de validación.' }),
          ),
        ),
        el(
          'aside',
          { clase: 'detalle__lateral' },
          tarjeta(
            'Código QR',
            el('div', { clase: 'qr' }, imagenQr.hidden ? marcadorQr : null, imagenQr),
            el(
              'div',
              { clase: 'cufe' },
              el('div', { clase: 'cufe__cabecera' }, el('span', { clase: 'cufe__etiqueta', texto: 'CUFE' }), copiar),
              el('code', { clase: 'cufe__valor', texto: factura.cufe }),
            ),
            verificacion
              ? el(
                  'a',
                  {
                    clase: 'boton boton--fantasma boton--bloque',
                    atributos: { href: verificacion.href, target: '_blank', rel: 'noopener noreferrer' },
                  },
                  icono('externo'),
                  el('span', { clase: 'boton__texto', texto: 'Ver página de verificación' }),
                )
              : null,
          ),
        ),
      ),
    );
    principal.querySelector('.encabezado__titulo')?.focus({ preventScroll: true });
  }

  async function recargar() {
    try {
      pintar(await api.obtenerFactura(id));
    } catch (error) {
      if (!activo || error.estado === 401) return;
      principal.replaceChildren(
        estadoVacio({
          titulo: error.estado === 404 ? 'Factura no encontrada' : 'No fue posible cargar la factura',
          texto: error.estado === 404 ? 'La factura no existe o no tiene acceso a ella.' : error.message,
          iconoNombre: 'alerta',
          accion: el('a', { clase: 'boton boton--secundario', atributos: { href: '#/facturas' } }, el('span', { clase: 'boton__texto', texto: 'Volver a facturas' })),
        }),
      );
      return;
    }
    if (!urlQr && !imagenQr.dataset.solicitado) {
      imagenQr.dataset.solicitado = '1';
      cargarQr();
    }
  }

  await recargar();
  return limpiar;
}
