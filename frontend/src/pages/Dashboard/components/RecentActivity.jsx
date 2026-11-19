import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '@/components/ui/StatusBadge/StatusBadge';
import {
  ArrowRightIcon,
  BarChartIcon,
  CheckIcon,
  DownloadIcon,
  MoreIcon,
  XIcon,
} from '@/components/icons';
import { urlPdfFactura } from '@/api/facturasService';
import { formatCOP, formatFechaHora } from '@/utils/format';
import styles from './RecentActivity.module.css';

export default function RecentActivity({ facturas, loading, error, busqueda, onPagar, onAnular }) {
  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <h2>
          <BarChartIcon width={26} height={26} />
          Actividad reciente
        </h2>
        <Link to="/facturas" className={styles.all}>
          Ver todas <ArrowRightIcon width={16} height={16} />
        </Link>
      </header>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Factura N°</th>
              <th>Cliente</th>
              <th>Total</th>
              <th>Estado</th>
              <th className={styles.center}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading && <EstadoFila texto="Cargando facturas…" />}
            {!loading && error && <EstadoFila texto={error} error />}
            {!loading && !error && facturas.length === 0 && (
              <EstadoFila
                texto={busqueda ? `Sin resultados para “${busqueda}”` : 'Aún no has emitido facturas'}
              />
            )}
            {!loading &&
              !error &&
              facturas.map((f) => (
                <tr key={f.id}>
                  <td>{formatFechaHora(f.fecha_emision)}</td>
                  <td className={styles.numero}>{f.numero}</td>
                  <td>{f.cliente_nombre}</td>
                  <td className={styles.total}>{formatCOP(f.total)}</td>
                  <td>
                    <StatusBadge estado={f.estado} />
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <a
                        href={urlPdfFactura(f.id)}
                        target="_blank"
                        rel="noreferrer"
                        className={styles.iconBtn}
                        aria-label={`Descargar PDF de ${f.numero}`}
                        title="Descargar PDF"
                      >
                        <DownloadIcon width={20} height={20} />
                      </a>
                      <RowMenu factura={f} onPagar={onPagar} onAnular={onAnular} />
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EstadoFila({ texto, error }) {
  return (
    <tr>
      <td colSpan={6} className={`${styles.empty} ${error ? styles.error : ''}`}>
        {texto}
      </td>
    </tr>
  );
}

/** Menú ⋮ por fila: marcar como pagada / anular */
function RowMenu({ factura, onPagar, onAnular }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const cerrar = (e) => !ref.current?.contains(e.target) && setOpen(false);
    document.addEventListener('mousedown', cerrar);
    return () => document.removeEventListener('mousedown', cerrar);
  }, [open]);

  const ejecutar = (accion) => {
    setOpen(false);
    accion(factura);
  };

  const puedePagar = factura.estado === 'EMITIDA';
  const puedeAnular = factura.estado !== 'ANULADA';

  return (
    <div className={styles.menuWrap} ref={ref}>
      <button
        className={styles.iconBtn}
        onClick={() => setOpen((v) => !v)}
        aria-label={`Más acciones para ${factura.numero}`}
        aria-expanded={open}
      >
        <MoreIcon width={20} height={20} />
      </button>
      {open && (
        <div className={styles.menu} role="menu">
          <button role="menuitem" disabled={!puedePagar} onClick={() => ejecutar(onPagar)}>
            <CheckIcon width={16} height={16} /> Marcar como pagada
          </button>
          <button
            role="menuitem"
            className={styles.danger}
            disabled={!puedeAnular}
            onClick={() => ejecutar(onAnular)}
          >
            <XIcon width={16} height={16} /> Anular factura
          </button>
        </div>
      )}
    </div>
  );
}
