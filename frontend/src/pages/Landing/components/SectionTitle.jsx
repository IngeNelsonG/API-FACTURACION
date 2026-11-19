import styles from './SectionTitle.module.css';

/** Título de sección con líneas a los lados, como en el mockup */
export default function SectionTitle({ titulo, subtitulo }) {
  return (
    <header className={styles.wrap}>
      <h2 className={styles.title}>{titulo}</h2>
      {subtitulo && <p className={styles.subtitle}>{subtitulo}</p>}
    </header>
  );
}
