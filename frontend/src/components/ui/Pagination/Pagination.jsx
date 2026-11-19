import { ChevronLeftIcon, ChevronRightIcon } from '@/components/icons';
import styles from './Pagination.module.css';

/** Números a mostrar: 1 … 4 5 6 … 12 */
function paginasVisibles(actual, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const set = new Set([1, total, actual - 1, actual, actual + 1]);
  const nums = [...set].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
  const out = [];
  nums.forEach((n, i) => {
    if (i > 0 && n - nums[i - 1] > 1) out.push('…');
    out.push(n);
  });
  return out;
}

export default function Pagination({ pagina, totalPaginas, total, desde, hasta, etiqueta = 'registros', onChange }) {
  return (
    <div className={styles.bar}>
      <p className={styles.info}>
        {total === 0 ? `0 ${etiqueta}` : `Mostrando ${desde}–${hasta} de ${total} ${etiqueta}`}
      </p>

      {totalPaginas > 1 && (
        <nav className={styles.pages} aria-label="Paginación">
          <button className={styles.nav} disabled={pagina === 1} onClick={() => onChange(pagina - 1)}>
            <ChevronLeftIcon width={16} height={16} /> Anterior
          </button>
          {paginasVisibles(pagina, totalPaginas).map((n, i) =>
            n === '…' ? (
              <span key={`e${i}`} className={styles.ellipsis}>
                …
              </span>
            ) : (
              <button
                key={n}
                className={`${styles.num} ${n === pagina ? styles.active : ''}`}
                aria-current={n === pagina ? 'page' : undefined}
                onClick={() => onChange(n)}
              >
                {n}
              </button>
            ),
          )}
          <button className={styles.nav} disabled={pagina === totalPaginas} onClick={() => onChange(pagina + 1)}>
            Siguiente <ChevronRightIcon width={16} height={16} />
          </button>
        </nav>
      )}
    </div>
  );
}
