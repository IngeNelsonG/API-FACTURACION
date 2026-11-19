import { CheckIcon, ClockIcon, XIcon } from '@/components/icons';
import styles from './StatusBadge.module.css';

// Estado del back → etiqueta y estilo visual
const ESTADOS = {
  PAGADA: { label: 'Pagada', className: styles.paid, Icon: CheckIcon },
  EMITIDA: { label: 'Pendiente', className: styles.pending, Icon: ClockIcon },
  ANULADA: { label: 'Anulada', className: styles.void, Icon: XIcon },
};

export default function StatusBadge({ estado }) {
  const cfg = ESTADOS[estado] || ESTADOS.EMITIDA;
  const { Icon } = cfg;
  return (
    <span className={`${styles.badge} ${cfg.className}`}>
      <span className={styles.dot}>
        <Icon width={11} height={11} />
      </span>
      {cfg.label}
    </span>
  );
}
