import { TrendDownIcon, TrendUpIcon } from '@/components/icons';
import styles from './StatCard.module.css';

/**
 * Tarjeta de indicador.
 * variant: "blue" (informativa) | "urgent" (vinotinto, llama la atención) | "gray" (neutral)
 */
export default function StatCard({ variant = 'blue', Icon, label, total, variacion, loading }) {
  return (
    <article className={`${styles.card} ${styles[variant]}`}>
      <span className={styles.iconWrap}>
        <Icon width={30} height={30} />
      </span>
      <div className={styles.body}>
        <p className={styles.label}>{label}</p>
        <div className={styles.row}>
          <strong className={styles.total}>{loading ? '–' : total}</strong>
          {!loading && <Trend variacion={variacion} />}
        </div>
      </div>
    </article>
  );
}

function Trend({ variacion }) {
  if (variacion === null) {
    return (
      <span className={`${styles.trend} ${styles.neutral}`} title="Primer mes con registros">
        Nuevo
      </span>
    );
  }
  const sube = variacion >= 0;
  const Icon = sube ? TrendUpIcon : TrendDownIcon;
  return (
    <span className={`${styles.trend} ${sube ? styles.up : styles.down}`} title="vs. mes anterior">
      <Icon width={15} height={15} />
      {sube ? '+' : ''}
      {variacion}%
    </span>
  );
}
