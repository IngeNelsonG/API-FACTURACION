import { http, ApiError, API_URL } from './httpClient';
import { loadSession, clearSession } from '@/utils/storage';

/** GET /facturas → lista con cliente_nombre, cliente_cedula, cliente_correo (scoped por rol) */
export const getFacturas = () => http('/facturas');

/** POST /facturas → { mensaje, factura, desglose_tributario } */
export const crearFactura = ({ persona_id, concepto, subtotal }) =>
  http('/facturas', { method: 'POST', body: { persona_id, concepto, subtotal } });

/** PATCH /facturas/<id>/pagar → EMITIDA pasa a PAGADA */
export const pagarFactura = (id) => http(`/facturas/${id}/pagar`, { method: 'PATCH' });

/** DELETE /facturas/<id> → la factura pasa a ANULADA */
export const anularFactura = (id) => http(`/facturas/${id}`, { method: 'DELETE' });

/** GET /facturas/<id>/pdf con Bearer token → abre o descarga el PDF */
export async function descargarPdfFactura(factura) {
  const session = loadSession();
  const headers = {};
  if (session?.token) headers.Authorization = `Bearer ${session.token}`;

  let response;
  try {
    response = await fetch(`${API_URL}/facturas/${factura.id}/pdf`, { headers });
  } catch {
    throw new ApiError('No se pudo conectar con el servidor. ¿Está corriendo la API?', 0);
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) clearSession();
    throw new ApiError(data.error || 'No se pudo descargar el PDF', response.status);
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const win = window.open(blobUrl, '_blank', 'noopener,noreferrer');
  if (!win) {
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `Factura_${factura.numero || factura.id}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

/** POST /facturas/<id>/enviar-correo → { enviado, modo, destinatario, mensaje } */
export const enviarFacturaCorreo = (id) => http(`/facturas/${id}/enviar-correo`, { method: 'POST' });
