import { useEffect, useRef, useState } from 'react';
import StatusBadge from '@/components/ui/StatusBadge/StatusBadge';
import {
  CheckIcon,
  DownloadIcon,
  EyeOpenIcon,
  MoreIcon,
  ShareIcon,
  XIcon,
} from '@/components/icons';
import { formatCOP, formatFecha } from '@/utils/format';
import styles from './FacturasTable.module.css';

export default function FacturasTable({ facturas, loading, error, vacio, onVer, onDescargar, onEnviar, onPagar, onAnular }) {
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>N° Factura</th>
            <th>Fecha de emisión</th>
            <th>Cliente</th>
            <th>Total</th>
            <th>Estado</th>
            <th className={styles.center}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {loading && <Mensaje texto="Cargando facturas…" />}
          {!loading && error && <Mensaje texto={error} error />}
          {!loading && !error && facturas.length === 0 && <Mensaje texto={vacio} />}
          {!loading &&
            !error &&
            facturas.map((f) => (
              <tr key={f.id}>
                <td className={styles.numero}>{f.numero}</td>
                <td>{formatFecha(f.fecha_emision)}</td>
                <td className={styles.cliente}>{f.cliente_nombre}</td>
                <td className={styles.total}>{formatCOP(f.total)}</td>
                <td>
                  <StatusBadge estado={f.estado} />
                </td>
                <td>
                  <div className={styles.actions}>
                    <button className={styles.iconBtn} onClick={() => onVer(f)} title="Ver detalle" aria-label={`Ver ${f.numero}`}>
                      <EyeOpenIcon width={20} height={20} />
                    </button>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => onDescargar(f)}
                      title="Descargar PDF"
                      aria-label={`Descargar PDF de ${f.numero}`}
                    >
                      <DownloadIcon width={20} height={20} />
                    </button>
                    <button
                      className={styles.iconBtn}
                      onClick={() => onEnviar(f)}
                      disabled={f.estado === 'ANULADA'}
                      title={f.estado === 'ANULADA' ? 'No se envían facturas anuladas' : `Enviar a ${f.cliente_correo}`}
                      aria-label={`Enviar ${f.numero} por correo`}
                    >
                      <ShareIcon width={20} height={20} />
                    </button>
                    <RowMenu factura={f} onPagar={onPagar} onAnular={onAnular} />
                  </div>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

function Mensaje({ texto, error }) {
  return (
    <tr>
      <td colSpan={6} className={`${styles.empty} ${error ? styles.error : ''}`}>
        {texto}
      </td>
    </tr>
  );
}

/** Menú ⋮: marcar como pagada / anular */
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
          <button role="menuitem" disabled={factura.estado !== 'EMITIDA'} onClick={() => ejecutar(onPagar)}>
            <CheckIcon width={16} height={16} /> Marcar como pagada
          </button>
          <button
            role="menuitem"
            className={styles.danger}
            disabled={factura.estado === 'ANULADA'}
            onClick={() => ejecutar(onAnular)}
          >
            <XIcon width={16} height={16} /> Anular factura
          </button>
        </div>
      )}
    </div>
  );
}
