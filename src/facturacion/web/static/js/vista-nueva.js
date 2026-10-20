// Formulario de emisión de factura con líneas dinámicas y vista previa de totales.
// Los totales se calculan en centavos (BigInt) solo como referencia: el servidor
// recalcula y es la fuente de verdad.

import { api } from './api.js';
import { boton, campo, conCarga, encabezadoPagina, marcarError, notificar } from './ui.js';
import {
  aUnidades,
  dividirRedondeando,
  el,
  formatearCentavos,
  hoyIso,
  icono,
  MEDIOS_PAGO,
  TIPOS_DOCUMENTO,
} from './utils.js';

const MAX_LINEAS = 500;
const RE_DOCUMENTO = /^[0-9A-Za-z-]{3,20}$/;
const RE_CODIGO = /^[0-9A-Za-z._-]{0,50}$/;
const RE_TELEFONO = /^[0-9+() -]{0,20}$/;
const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UN_MILLON = 1000000n;

function seccion(titulo, descripcion, ...contenido) {
  return el(
    'fieldset',
    { clase: 'tarjeta seccion' },
    el('legend', { clase: 'seccion__titulo', texto: titulo }),
    descripcion ? el('p', { clase: 'seccion__descripcion', texto: descripcion }) : null,
    ...contenido,
  );
}

function filaResumen(etiqueta, clase = '') {
  const valor = el('dd', { clase: 'numero', texto: formatearCentavos(0n) });
  const raiz = el('div', { clase: `resumen__fila ${clase}`.trim() }, el('dt', { texto: etiqueta }), valor);
  return { raiz, valor };
}

export function renderizarNuevaFactura(principal, { navegar }) {
  // ------------------------------------------------------------ adquiriente
  const adq = {
    tipo_documento: campo({ etiqueta: 'Tipo de documento', nombre: 'tipo_documento', control: 'select', opciones: TIPOS_DOCUMENTO, requerido: true, valor: '13' }),
    numero_documento: campo({ etiqueta: 'Número de documento', nombre: 'numero_documento', requerido: true, ayuda: 'Sin puntos ni espacios.', atributos: { maxlength: '20', autocomplete: 'off', spellcheck: 'false' } }),
    dv: campo({ etiqueta: 'DV', nombre: 'dv', requerido: true, ayuda: 'Dígito de verificación.', atributos: { maxlength: '1', inputmode: 'numeric', autocomplete: 'off' }, clase: 'campo--angosto' }),
    nombre: campo({ etiqueta: 'Nombre o razón social', nombre: 'nombre', requerido: true, atributos: { maxlength: '300', autocomplete: 'organization' }, clase: 'campo--ancho' }),
    email: campo({ etiqueta: 'Correo electrónico', nombre: 'email', tipo: 'email', requerido: true, ayuda: 'Recibirá el PDF y el XML de la factura.', atributos: { maxlength: '254', autocomplete: 'email', spellcheck: 'false' } }),
    telefono: campo({ etiqueta: 'Teléfono', nombre: 'telefono', tipo: 'tel', atributos: { maxlength: '20', autocomplete: 'tel' } }),
    direccion: campo({ etiqueta: 'Dirección', nombre: 'direccion', atributos: { maxlength: '200', autocomplete: 'street-address' }, clase: 'campo--ancho' }),
    ciudad: campo({ etiqueta: 'Ciudad', nombre: 'ciudad', valor: 'Bogotá, D.C.', atributos: { maxlength: '100' } }),
    codigo_municipio: campo({ etiqueta: 'Código municipio (DANE)', nombre: 'codigo_municipio', valor: '11001', requerido: true, atributos: { maxlength: '5', inputmode: 'numeric' } }),
    departamento: campo({ etiqueta: 'Departamento', nombre: 'departamento', valor: 'Bogotá', atributos: { maxlength: '100' } }),
    codigo_departamento: campo({ etiqueta: 'Código departamento', nombre: 'codigo_departamento', valor: '11', requerido: true, atributos: { maxlength: '2', inputmode: 'numeric' } }),
  };
  const actualizarDv = () => {
    const esNit = adq.tipo_documento.control.value === '31';
    adq.dv.raiz.hidden = !esNit;
    if (!esNit) {
      adq.dv.control.value = '';
      marcarError(adq.dv, '');
    }
  };
  adq.tipo_documento.control.addEventListener('change', actualizarDv);
  actualizarDv();

  const seccionAdquiriente = seccion(
    'Adquiriente',
    'Datos de quien recibe la factura, tal como aparecen en su RUT o documento.',
    el(
      'div',
      { clase: 'rejilla' },
      el('div', { clase: 'grupo-documento campo--ancho' }, adq.tipo_documento.raiz, adq.numero_documento.raiz, adq.dv.raiz),
      adq.nombre.raiz,
      adq.email.raiz,
      adq.telefono.raiz,
      adq.direccion.raiz,
      adq.ciudad.raiz,
      adq.departamento.raiz,
      adq.codigo_municipio.raiz,
      adq.codigo_departamento.raiz,
    ),
  );

  // ------------------------------------------------------------------ líneas
  const lineas = [];
  const listaLineas = el('ol', { clase: 'lineas' });
  const botonAgregar = boton('Agregar ítem', { variante: 'secundario', icono: 'mas', alPulsar: () => agregarLinea(true) });

  function reindexar() {
    lineas.forEach((linea, indice) => {
      linea.titulo.textContent = `Ítem ${indice + 1}`;
      linea.quitar.disabled = lineas.length === 1;
      linea.quitar.setAttribute('aria-label', `Quitar ítem ${indice + 1}`);
    });
    botonAgregar.disabled = lineas.length >= MAX_LINEAS;
  }

  function agregarLinea(enfocar = false) {
    if (lineas.length >= MAX_LINEAS) return;
    const campos = {
      descripcion: campo({ etiqueta: 'Descripción', nombre: 'descripcion', requerido: true, atributos: { maxlength: '300' }, clase: 'linea__descripcion' }),
      codigo: campo({ etiqueta: 'Código', nombre: 'codigo', atributos: { maxlength: '50', spellcheck: 'false' }, clase: 'linea__codigo' }),
      cantidad: campo({ etiqueta: 'Cantidad', nombre: 'cantidad', requerido: true, valor: '1', atributos: { inputmode: 'decimal', maxlength: '22' }, clase: 'linea__cantidad' }),
      precio_unitario: campo({ etiqueta: 'Precio unitario', nombre: 'precio_unitario', requerido: true, atributos: { inputmode: 'decimal', maxlength: '16', placeholder: '0.00' }, clase: 'linea__precio' }),
      porcentaje_iva: campo({ etiqueta: 'IVA', nombre: 'porcentaje_iva', control: 'select', opciones: [['19', '19 %'], ['5', '5 %'], ['0', '0 % (excluido)']], valor: '19', clase: 'linea__iva' }),
    };
    const titulo = el('span', { clase: 'linea__titulo' });
    const importe = el('span', { clase: 'linea__importe numero', texto: formatearCentavos(0n) });
    const quitar = el(
      'button',
      { clase: 'boton-icono boton-icono--peligro', atributos: { type: 'button' } },
      icono('basura'),
    );
    const raiz = el(
      'li',
      { clase: 'linea' },
      el('div', { clase: 'linea__cabecera' }, titulo, el('div', { clase: 'linea__derecha' }, importe, quitar)),
      el('div', { clase: 'linea__campos' }, Object.values(campos).map((c) => c.raiz)),
    );
    const linea = { raiz, campos, titulo, importe, quitar };
    quitar.addEventListener('click', () => {
      const indice = lineas.indexOf(linea);
      if (indice < 0 || lineas.length === 1) return;
      lineas.splice(indice, 1);
      raiz.remove();
      reindexar();
      recalcular();
      (lineas[Math.min(indice, lineas.length - 1)]?.campos.descripcion.control || botonAgregar).focus();
    });
    for (const c of Object.values(campos)) c.control.addEventListener('input', recalcular);
    lineas.push(linea);
    listaLineas.append(raiz);
    reindexar();
    recalcular();
    if (enfocar) campos.descripcion.control.focus();
  }

  const seccionLineas = seccion(
    'Ítems',
    'Productos o servicios facturados. Cantidad con hasta 6 decimales y precio con hasta 2.',
    listaLineas,
    el('div', { clase: 'seccion__pie' }, botonAgregar),
  );

  // -------------------------------------------------------------------- pago
  const pago = {
    forma_pago: campo({ etiqueta: 'Forma de pago', nombre: 'forma_pago', control: 'select', opciones: [['1', 'Contado'], ['2', 'Crédito']], valor: '1' }),
    fecha_vencimiento: campo({ etiqueta: 'Fecha de vencimiento', nombre: 'fecha_vencimiento', tipo: 'date', requerido: true, atributos: { min: hoyIso() } }),
    medio_pago: campo({ etiqueta: 'Medio de pago', nombre: 'medio_pago', control: 'select', opciones: MEDIOS_PAGO, valor: '10' }),
  };
  const actualizarVencimiento = () => {
    const credito = pago.forma_pago.control.value === '2';
    pago.fecha_vencimiento.raiz.hidden = !credito;
    if (!credito) marcarError(pago.fecha_vencimiento, '');
  };
  pago.forma_pago.control.addEventListener('change', actualizarVencimiento);
  actualizarVencimiento();

  const notas = campo({ etiqueta: 'Notas', nombre: 'notas', control: 'textarea', ayuda: 'Opcional. Máximo 1000 caracteres.', atributos: { maxlength: '1000', rows: '3' }, clase: 'campo--ancho' });
  const seccionPago = seccion(
    'Pago y notas',
    null,
    el('div', { clase: 'rejilla' }, pago.forma_pago.raiz, pago.medio_pago.raiz, pago.fecha_vencimiento.raiz, notas.raiz),
  );

  // ----------------------------------------------------------------- resumen
  const filas = {
    subtotal: filaResumen('Subtotal'),
    iva5: filaResumen('IVA 5 %'),
    iva19: filaResumen('IVA 19 %'),
    total: filaResumen('Total', 'resumen__fila--total'),
  };
  const conteo = el('p', { clase: 'resumen__conteo' });
  const emitir = boton('Emitir factura', { tipo: 'submit', icono: 'documento', clase: 'boton--bloque' });
  const resumen = el(
    'aside',
    { clase: 'tarjeta resumen', atributos: { 'aria-labelledby': 'titulo-resumen' } },
    el('h2', { clase: 'resumen__titulo', texto: 'Resumen', atributos: { id: 'titulo-resumen' } }),
    conteo,
    el('dl', { clase: 'resumen__lista', atributos: { 'aria-live': 'polite' } }, Object.values(filas).map((f) => f.raiz)),
    el('p', { clase: 'resumen__nota', texto: 'Valores estimados. La API calcula los montos definitivos al emitir.' }),
    emitir,
    el('a', { clase: 'boton boton--fantasma boton--bloque', atributos: { href: '#/facturas' } }, el('span', { clase: 'boton__texto', texto: 'Cancelar' })),
  );

  function recalcular() {
    let subtotal = 0n;
    const iva = { 5: 0n, 19: 0n };
    for (const linea of lineas) {
      const cantidad = aUnidades(linea.campos.cantidad.control.value, 6);
      const precio = aUnidades(linea.campos.precio_unitario.control.value, 2);
      const tarifa = BigInt(linea.campos.porcentaje_iva.control.value);
      if (cantidad === null || precio === null) {
        linea.importe.textContent = '—';
        continue;
      }
      // Igual que el servidor: subtotal e IVA redondeados (ROUND_HALF_UP) por línea.
      const sub = dividirRedondeando(cantidad * precio, UN_MILLON);
      const impuesto = dividirRedondeando(sub * tarifa, 100n);
      linea.importe.textContent = formatearCentavos(sub);
      subtotal += sub;
      if (tarifa > 0n) iva[String(tarifa)] += impuesto;
    }
    filas.subtotal.valor.textContent = formatearCentavos(subtotal);
    filas.iva5.valor.textContent = formatearCentavos(iva[5]);
    filas.iva19.valor.textContent = formatearCentavos(iva[19]);
    filas.total.valor.textContent = formatearCentavos(subtotal + iva[5] + iva[19]);
    conteo.textContent = `${lineas.length} ${lineas.length === 1 ? 'ítem' : 'ítems'}`;
  }

  // -------------------------------------------------------------- validación
  const resumenErrores = el('div', { clase: 'alerta alerta--error', atributos: { role: 'alert', tabindex: '-1', hidden: true } });

  function validar() {
    const errores = [];
    let prefijo = '';
    const exigir = (c, condicion, mensaje) => {
      if (!condicion) errores.push([c, mensaje, `${prefijo}${etiquetaDe(c)}`]);
    };
    const valor = (c) => c.control.value.trim();

    exigir(adq.numero_documento, RE_DOCUMENTO.test(valor(adq.numero_documento)), 'Entre 3 y 20 caracteres: letras, números o guion.');
    if (adq.tipo_documento.control.value === '31') exigir(adq.dv, /^\d$/.test(valor(adq.dv)), 'El DV es un dígito (0-9).');
    exigir(adq.nombre, valor(adq.nombre).length >= 1, 'Ingrese el nombre o la razón social.');
    exigir(adq.email, RE_EMAIL.test(valor(adq.email)) && adq.email.control.checkValidity(), 'Ingrese un correo electrónico válido.');
    exigir(adq.telefono, RE_TELEFONO.test(valor(adq.telefono)), 'Solo números, espacios y + ( ) -.');
    exigir(adq.codigo_municipio, /^\d{5}$/.test(valor(adq.codigo_municipio)), 'Código DANE de 5 dígitos (p. ej. 11001).');
    exigir(adq.codigo_departamento, /^\d{2}$/.test(valor(adq.codigo_departamento)), 'Código de 2 dígitos (p. ej. 11).');

    for (const [indice, linea] of lineas.entries()) {
      const c = linea.campos;
      prefijo = `Ítem ${indice + 1} · `;
      exigir(c.descripcion, valor(c.descripcion).length >= 1, 'Ingrese la descripción.');
      exigir(c.codigo, RE_CODIGO.test(valor(c.codigo)), 'Letras, números, punto, guion o guion bajo.');
      const cantidad = aUnidades(valor(c.cantidad), 6);
      exigir(c.cantidad, cantidad !== null && cantidad > 0n, 'Mayor que 0, hasta 6 decimales.');
      exigir(c.precio_unitario, aUnidades(valor(c.precio_unitario), 2) !== null, 'Valor ≥ 0 con hasta 2 decimales.');
    }

    prefijo = '';
    if (pago.forma_pago.control.value === '2') {
      exigir(pago.fecha_vencimiento, Boolean(pago.fecha_vencimiento.control.value), 'Obligatoria para pagos a crédito.');
    }
    return errores;
  }

  function etiquetaDe(c) {
    return c.raiz.querySelector('label')?.firstChild?.textContent || '';
  }

  function mostrarErrores(errores, titulo) {
    for (const [c, mensaje] of errores) if (c) marcarError(c, mensaje);
    resumenErrores.replaceChildren(
      el('p', { clase: 'alerta__titulo', texto: titulo }),
      el('ul', {}, errores.map(([, mensaje, etiqueta]) => el('li', { texto: etiqueta ? `${etiqueta}: ${mensaje}` : mensaje }))),
    );
    resumenErrores.hidden = false;
    const primero = errores.find(([c]) => c)?.[0];
    (primero ? primero.control : resumenErrores).focus();
  }

  /** Traduce los errores del servidor ({campo, mensaje}) a los campos del formulario. */
  function erroresDelServidor(campos) {
    return campos.map(({ campo: ruta, mensaje }) => {
      const limpio = mensaje.replace(/^Value error, /, '');
      const partes = ruta.split('.');
      let destino = null;
      let etiqueta = ruta || 'Factura';
      if (partes[0] === 'adquiriente') {
        destino = adq[partes[1]] || (adq.tipo_documento.control.value === '31' ? adq.dv : null);
        etiqueta = destino ? etiquetaDe(destino) : 'Adquiriente';
      } else if (partes[0] === 'lineas' && partes.length >= 3) {
        const linea = lineas[Number(partes[1])];
        destino = linea?.campos[partes[2]] || null;
        etiqueta = `Ítem ${Number(partes[1]) + 1}${destino ? ` · ${etiquetaDe(destino)}` : ''}`;
      } else if (pago[partes[0]] || partes[0] === 'notas') {
        destino = pago[partes[0]] || notas;
        etiqueta = etiquetaDe(destino);
      } else if (ruta === '' && pago.forma_pago.control.value === '2') {
        destino = pago.fecha_vencimiento;
        etiqueta = 'Fecha de vencimiento';
      }
      return [destino, limpio, etiqueta];
    });
  }

  function construirPayload() {
    const v = (c) => c.control.value.trim();
    const adquiriente = {
      tipo_documento: adq.tipo_documento.control.value,
      numero_documento: v(adq.numero_documento),
      nombre: v(adq.nombre),
      email: v(adq.email),
      direccion: v(adq.direccion),
      ciudad: v(adq.ciudad),
      codigo_municipio: v(adq.codigo_municipio),
      departamento: v(adq.departamento),
      codigo_departamento: v(adq.codigo_departamento),
      telefono: v(adq.telefono),
    };
    if (adquiriente.tipo_documento === '31') adquiriente.dv = v(adq.dv);
    const datos = {
      adquiriente,
      lineas: lineas.map(({ campos: c }) => ({
        descripcion: v(c.descripcion),
        codigo: v(c.codigo),
        cantidad: v(c.cantidad).replace(',', '.'),
        precio_unitario: v(c.precio_unitario).replace(',', '.'),
        porcentaje_iva: c.porcentaje_iva.control.value,
      })),
      forma_pago: pago.forma_pago.control.value,
      medio_pago: pago.medio_pago.control.value,
      notas: v(notas),
    };
    if (datos.forma_pago === '2') datos.fecha_vencimiento = pago.fecha_vencimiento.control.value;
    return datos;
  }

  const formulario = el(
    'form',
    { clase: 'nueva-factura', atributos: { novalidate: true, 'aria-label': 'Nueva factura' } },
    el('div', { clase: 'nueva-factura__principal' }, resumenErrores, seccionAdquiriente, seccionLineas, seccionPago),
    resumen,
  );

  formulario.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    resumenErrores.hidden = true;
    const errores = validar();
    if (errores.length) {
      mostrarErrores(errores, `Revise ${errores.length === 1 ? 'el campo marcado' : `los ${errores.length} campos marcados`}.`);
      return;
    }
    try {
      const factura = await conCarga(emitir, () => api.emitirFactura(construirPayload()), 'Emitiendo…');
      notificar(`Factura ${factura.numero} emitida.`);
      navegar(`#/facturas/${encodeURIComponent(factura.id)}`);
    } catch (error) {
      if (error.estado === 401) return;
      if (error.campos?.length) {
        mostrarErrores(erroresDelServidor(error.campos), 'La API rechazó algunos datos:');
      } else {
        mostrarErrores([[null, error.message]], 'No fue posible emitir la factura.');
        notificar(error.message, 'error');
      }
    }
  });

  agregarLinea();
  principal.replaceChildren(
    encabezadoPagina('Nueva factura', {
      subtitulo: 'Se firmará y enviará a la DIAN al emitirla.',
      volver: { href: '#/facturas', texto: 'Facturas' },
    }),
    formulario,
  );
  adq.numero_documento.control.focus();
}
