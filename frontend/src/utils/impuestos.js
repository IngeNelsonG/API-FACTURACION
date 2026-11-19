// Tarifas usadas por el back (facturacion_servicio.calcular_impuestos)
export const TARIFA_IVA = 0.19; // Tarifa general del IVA (art. 468 E.T.)
export const TARIFA_GMF = 0.004; // 4x1000 – Gravamen a los Movimientos Financieros (art. 872 E.T.)

const redondear = (n) => Math.round(n * 100) / 100;

/**
 * Misma liquidación del back:
 * - total = subtotal + IVA 19%
 * - gmf  = 0.4% del total. Es INFORMATIVO: lo retiene el banco al mover el dinero
 *          para pagar la factura (base = valor total de la transacción, art. 874 E.T.).
 *          No se suma al total de la factura.
 */
export function liquidar(subtotal) {
  const base = redondear(Number(subtotal) || 0);
  const iva = redondear(base * TARIFA_IVA);
  const total = redondear(base + iva);
  const gmf = redondear(total * TARIFA_GMF);
  return { base, iva, total, gmf };
}
