import { parseFechaSqlite } from './format';

/*
 * Ciclo de vida en el back:
 *   EMITIDA (o PENDIENTE) → pendiente de pago
 *   PAGADA                → pagada
 *   ANULADA               → anulada
 *
 * "total" = TODAS las facturas del grupo (no solo las del mes).
 * "variacion" = % del mes actual frente al anterior; null si el mes anterior
 * no tiene registros (la tarjeta muestra "Nuevo").
 */

const ESTADOS = {
  emitidas: ['EMITIDA', 'PENDIENTE', 'PAGADA'],
  pendientes: ['EMITIDA', 'PENDIENTE'],
  pagadas: ['PAGADA'],
  anuladas: ['ANULADA'],
};

const mismoMes = (fecha, ref) =>
  fecha && fecha.getMonth() === ref.getMonth() && fecha.getFullYear() === ref.getFullYear();

function variacion(actual, anterior) {
  if (anterior === 0) return actual > 0 ? null : 0;
  return Math.round(((actual - anterior) / anterior) * 100);
}

export function calcularEstadisticas(facturas = [], hoy = new Date()) {
  const mesAnterior = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1);

  return Object.fromEntries(
    Object.entries(ESTADOS).map(([clave, valores]) => {
      const grupo = facturas.filter((f) => valores.includes(String(f.estado || '').toUpperCase()));
      const fechas = grupo.map((f) => parseFechaSqlite(f.fecha_emision || f.fecha));
      const actual = fechas.filter((d) => mismoMes(d, hoy)).length;
      const anterior = fechas.filter((d) => mismoMes(d, mesAnterior)).length;
      return [clave, { total: grupo.length, variacion: variacion(actual, anterior) }];
    }),
  );
}
