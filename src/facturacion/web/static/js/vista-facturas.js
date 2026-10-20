// Listado paginado de facturas.

import { api } from './api.js';
import { boton, cargando, encabezadoPagina, estadoVacio, insigniaEstado, notificar } from './ui.js';
import { el, formatearFecha, formatearMoneda, icono } from './utils.js';

const POR_PAGINA = 20;

function enlaceNueva() {
  return el(
    'a',
    { clase: 'boton boton--primario', atributos: { href: '#/facturas/nueva' } },
    icono('mas'),
    el('span', { clase: 'boton__texto', texto: 'Nueva factura' }),
  );
}

function celda(etiqueta, contenido, clase = '') {
  return el('td', { clase, datos: { etiqueta } }, contenido);
}

function fila(factura, navegar) {
  const destino = `#/facturas/${encodeURIComponent(factura.id)}`;
  const tr = el(
    'tr',
    { clase: 'tabla__fila--enlace' },
    celda('Número', el('a', { clase: 'enlace-fuerte', texto: factura.numero, atributos: { href: destino } })),
    celda('Fecha', formatearFecha(factura.fecha_emision)),
    celda(
      'Adquiriente',
      el(
        'div',
        { clase: 'celda-doble' },
        el('span', { clase: 'celda-doble__principal', texto: factura.adquiriente_nombre }),
        el('span', { clase: 'celda-doble__secundario', texto: factura.adquiriente_documento }),
      ),
    ),
    celda('Total', formatearMoneda(factura.total), 'numero'),
    celda('Estado', insigniaEstado(factura.estado)),
  );
  // Toda la fila es clicable; el enlace del número mantiene la navegación por teclado.
  tr.addEventListener('click', (evento) => {
    if (evento.target.closest('a')) return;
    navegar(destino);
  });
  return tr;
}

function paginacion(pagina, total, irA) {
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const desde = total === 0 ? 0 : (pagina - 1) * POR_PAGINA + 1;
  const hasta = Math.min(total, pagina * POR_PAGINA);
  const anterior = boton('Anterior', { variante: 'secundario', clase: 'boton--pequeno', alPulsar: () => irA(pagina - 1) });
  const siguiente = boton('Siguiente', { variante: 'secundario', clase: 'boton--pequeno', alPulsar: () => irA(pagina + 1) });
  anterior.disabled = pagina <= 1;
  siguiente.disabled = pagina >= paginas;
  return el(
    'nav',
    { clase: 'paginacion', atributos: { 'aria-label': 'Paginación' } },
    el('p', { clase: 'paginacion__resumen', texto: `Mostrando ${desde}–${hasta} de ${total}` }),
    el('div', { clase: 'paginacion__botones' }, anterior, el('span', { clase: 'paginacion__pagina', texto: `Página ${pagina} de ${paginas}` }), siguiente),
  );
}

export async function renderizarFacturas(principal, { consulta, navegar }) {
  const pagina = Math.max(1, Number.parseInt(consulta.get('pagina') || '1', 10) || 1);
  const contenido = el('div', { clase: 'tarjeta tarjeta--sin-relleno' }, cargando('Cargando facturas…'));
  principal.replaceChildren(
    encabezadoPagina('Facturas', { subtitulo: 'Facturas electrónicas de venta emitidas', acciones: [enlaceNueva()] }),
    contenido,
  );

  let datos;
  try {
    datos = await api.listarFacturas(POR_PAGINA, (pagina - 1) * POR_PAGINA);
  } catch (error) {
    if (error.estado === 401) return;
    contenido.replaceChildren(
      estadoVacio({
        titulo: 'No fue posible cargar las facturas',
        texto: error.message,
        iconoNombre: 'alerta',
        accion: boton('Reintentar', { variante: 'secundario', alPulsar: () => renderizarFacturas(principal, { consulta, navegar }) }),
      }),
    );
    notificar(error.message, 'error');
    return;
  }

  if (datos.total === 0) {
    contenido.replaceChildren(
      estadoVacio({ titulo: 'Aún no hay facturas', texto: 'Emita su primera factura electrónica de venta.', accion: enlaceNueva() }),
    );
    return;
  }
  if (datos.elementos.length === 0 && pagina > 1) {
    navegar('#/facturas');
    return;
  }

  const tabla = el(
    'table',
    { clase: 'tabla tabla--responsiva' },
    el('caption', { clase: 'solo-lectores', texto: 'Listado de facturas' }),
    el(
      'thead',
      {},
      el(
        'tr',
        {},
        ['Número', 'Fecha', 'Adquiriente', 'Total', 'Estado'].map((titulo) =>
          el('th', { texto: titulo, clase: titulo === 'Total' ? 'numero' : '', atributos: { scope: 'col' } }),
        ),
      ),
    ),
    el('tbody', {}, datos.elementos.map((factura) => fila(factura, navegar))),
  );
  contenido.replaceChildren(
    el('div', { clase: 'tabla__contenedor' }, tabla),
    paginacion(pagina, datos.total, (nueva) => navegar(nueva <= 1 ? '#/facturas' : `#/facturas?pagina=${nueva}`)),
  );
}
