import { Link } from 'react-router-dom';
import { ArrowRightIcon } from '@/components/icons';
import styles from './SecurityCard.module.css';

export default function SecurityCard() {
  return (
    <section className={styles.card}>
      <svg className={styles.badge} viewBox="0 0 48 56" aria-hidden>
        <path d="M24 2 4 9v16c0 13 8.6 24.4 20 29 11.4-4.6 20-16 20-29V9L24 2Z" fill="currentColor" />
        <path d="m15 28 6.5 6.5L33 22" fill="none" style={{ stroke: 'var(--surface)' }} strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <h2>Tu información está protegida</h2>
      <p>
        Cumplimos con los estándares
        <br />
        de seguridad de la DIAN.
      </p>
      <Link to="/configuracion" className={styles.more}>
        Conocer más <ArrowRightIcon width={16} height={16} />
      </Link>

      {/* Escudo grande decorativo */}
      <svg className={styles.deco} viewBox="0 0 120 140" aria-hidden>
        <path d="M60 6 12 22v38c0 32 20.6 60 48 72 27.4-12 48-40 48-72V22L60 6Z" fill="none" stroke="#7cc8f2" strokeWidth="5" />
        <path d="m38 70 15 15 30-32" fill="none" stroke="#7cc8f2" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </section>
  );
}
