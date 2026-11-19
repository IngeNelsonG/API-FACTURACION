import { http, API_URL } from './httpClient';

/** GET /facturas → lista con cliente_nombre, cliente_cedula, cliente_correo */
export const getFacturas = () => http('/facturas', { auth: false });

/** POST /facturas → { mensaje, factura, desglose_tributario } */
export const crearFactura = ({ persona_id, concepto, subtotal }) =>
  http('/facturas', { method: 'POST', body: { persona_id, concepto, subtotal } });

/** PATCH /facturas/<id>/pagar → EMITIDA pasa a PAGADA */
export const pagarFactura = (id) => http(`/facturas/${id}/pagar`, { method: 'PATCH' });

/** DELETE /facturas/<id> → la factura pasa a ANULADA */
export const anularFactura = (id) => http(`/facturas/${id}`, { method: 'DELETE' });

/** GET /facturas/<id>/pdf es público: se abre directo en otra pestaña */
export const urlPdfFactura = (id) => `${API_URL}/facturas/${id}/pdf`;

/** POST /facturas/<id>/enviar-correo → { enviado, modo, destinatario, mensaje } */
export const enviarFacturaCorreo = (id) => http(`/facturas/${id}/enviar-correo`, { method: 'POST' });
