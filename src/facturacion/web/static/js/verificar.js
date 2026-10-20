// Página pública de verificación (destino del QR). Lee el CUFE de la URL, consulta la
// API pública y muestra solo datos del emisor y del documento.

import { api } from './api.js';
import { insigniaEstado } from './ui.js';
import { el, formatearFecha, formatearMoneda, icono } from './utils.js';

const RE_CUFE = /^[0-9a-f]{96}$/;
const resultado = document.getElementById('resultado');

function estado(tono, nombreIcono, titulo, texto) {
  return el(
    'div',
    { clase: `verificacion verificacion--${tono}` },
    el('div', { clase: 'verificacion__icono' }, icono(nombreIcono)),
    el('h2', { clase: 'verificacion__titulo', texto: titulo }),
    texto ? el('p', { clase: 'verificacion__texto', texto }) : null,
  );
}

function fila(etiqueta, valor, clase = '') {
  return el('div', { clase: `datos__fila ${clase}`.trim() }, el('dt', { texto: etiqueta }), el('dd', {}, valor));
}

function terminar(...nodos) {
  resultado.replaceChildren(...nodos);
  resultado.setAttribute('aria-busy', 'false');
}

async function iniciar() {
  const segmento = decodeURIComponent(window.location.pathname.split('/').filter(Boolean).pop() || '');
  if (!RE_CUFE.test(segmento)) {
    terminar(estado('peligro', 'alerta', 'Código no válido', 'El enlace no contiene un CUFE válido (96 caracteres hexadecimales).'));
    return;
  }
  let factura;
  try {
    factura = await api.verificacion(segmento);
  } catch (error) {
    if (error.estado === 404 || error.estado === 422) {
      terminar(
        estado('peligro', 'alerta', 'Factura no encontrada', 'No existe una factura emitida por este sistema con el CUFE indicado. Verifique que escaneó el código completo.'),
        el('code', { clase: 'cufe__valor', texto: segmento }),
      );
    } else {
      terminar(estado('neutro', 'alerta', 'No fue posible verificar', error.message));
    }
    return;
  }

  const aceptada = factura.estado === 'aceptada';
  document.title = `Factura ${factura.numero} · Verificación`;
  terminar(
    aceptada
      ? estado('exito', 'check', 'Factura verificada', 'El documento fue emitido por este sistema y aceptado por la DIAN.')
      : estado('aviso', 'alerta', 'Factura registrada', 'El documento existe, pero no figura como aceptado por la DIAN.'),
    el('p', { clase: 'verificacion__total numero', texto: formatearMoneda(factura.total) }),
    el(
      'dl',
      { clase: 'datos datos--apilados' },
      fila('Número', factura.numero),
      fila('Fecha de emisión', formatearFecha(factura.fecha_emision)),
      fila('Estado', insigniaEstado(factura.estado)),
      fila('Emisor', factura.emisor_razon_social),
      fila('NIT del emisor', factura.emisor_nit),
      fila('CUFE', el('code', { clase: 'cufe__valor', texto: factura.cufe }), 'datos__fila--completa'),
    ),
  );
}

iniciar();
