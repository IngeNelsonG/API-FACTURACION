import Logo from '@/components/brand/Logo';
import styles from './BrandPanel.module.css';

/** Columna izquierda: logo, titular y mensaje de marca */
export default function BrandPanel() {
  return (
    <div className={styles.panel}>
      <Logo variant="light" />

      <div className={styles.copy}>
        <h1 className={styles.title}>
          Facturación
          <br />
          Electrónica
          <br />
          <span className={styles.accent}>para tu negocio</span>
        </h1>
        <span className={styles.rule} aria-hidden />
        <p className={styles.subtitle}>
          Organiza, factura y haz crecer
          <br />
          tus ideas.
        </p>
      </div>
    </div>
  );
}
