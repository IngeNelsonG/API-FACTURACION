import Modal from '@/components/ui/Modal/Modal';
import StatusBadge from '@/components/ui/StatusBadge/StatusBadge';
import { DownloadIcon, ShareIcon } from '@/components/icons';
import { formatCOP, formatFechaHora } from '@/utils/format';
import styles from './InvoiceDetailModal.module.css';

/** Detalle completo de una factura (lo que devuelve GET /facturas en cada fila) */
export default function InvoiceDetailModal({ factura, onClose, onEnviar, onDescargar }) {
  return (
    <Modal open={Boolean(factura)} title={factura ? `Factura ${factura.numero}` : ''} onClose={onClose}>
      {factura && (
        <div className={styles.body}>
          <div className={styles.head}>
            <span>{formatFechaHora(factura.fecha_emision)}</span>
            <StatusBadge estado={factura.estado} />
          </div>

          <section className={styles.block}>
            <h3>Cliente</h3>
            <p className={styles.strong}>{factura.cliente_nombre}</p>
            <p>CC {factura.cliente_cedula} · {factura.cliente_correo}</p>
          </section>

          <section className={styles.block}>
            <h3>Concepto</h3>
            <p>{factura.concepto}</p>
          </section>

          <dl className={styles.summary}>
            <div>
              <dt>Subtotal</dt>
              <dd>{formatCOP(factura.subtotal)}</dd>
            </div>
            <div>
              <dt>IVA (19%)</dt>
              <dd>{formatCOP(factura.iva)}</dd>
            </div>
            <div className={styles.grand}>
              <dt>Total</dt>
              <dd>{formatCOP(factura.total)}</dd>
            </div>
            <div className={styles.note}>
              <dt>4x1000 que retendrá el banco al pagar (no se suma)</dt>
              <dd>{formatCOP(factura.impuesto_4x1000)}</dd>
            </div>
          </dl>

          <section className={styles.block}>
            <h3>CUFE</h3>
            <code className={styles.cufe}>{factura.cufe}</code>
          </section>

          {Boolean(factura.correo_enviado) && (
            <p className={styles.sent}>✓ Ya se envió por correo al cliente</p>
          )}

          <div className={styles.actions}>
            <button className={styles.secondary} onClick={() => onDescargar(factura)}>
              <DownloadIcon width={18} height={18} /> Descargar PDF
            </button>
            <button
              className={styles.primary}
              disabled={factura.estado === 'ANULADA'}
              onClick={() => onEnviar(factura)}
            >
              <ShareIcon width={18} height={18} /> Enviar por correo
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
