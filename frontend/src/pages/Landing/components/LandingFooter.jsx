import Logo from '@/components/brand/Logo';
import styles from './LandingFooter.module.css';

export default function LandingFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.brandRow}>
        <Logo variant="brand" size="sm" showTagline={false} />
      </div>
      <p className={styles.copy}>
        © {new Date().getFullYear()} Alba · Facturación Electrónica · Cloud Computing — Grupo 5
      </p>
    </footer>
  );
}
