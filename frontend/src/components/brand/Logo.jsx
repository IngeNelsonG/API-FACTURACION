import styles from './Logo.module.css';

/** Logo Alba: documento con líneas de velocidad + texto. variant: "light" | "dark" */
export default function Logo({ variant = 'light', showTagline = true, size = 'lg' }) {
  return (
    <div className={`${styles.logo} ${styles[variant]} ${styles[size]}`}>
      <svg className={styles.mark} viewBox="0 0 520 320" fill="none" aria-hidden>
        <g stroke="currentColor" strokeWidth="36" strokeLinecap="round" strokeLinejoin="round">
          {/* Documento */}
          <path d="M185 22H338Q352 22 362 32L480 150Q490 160 492 172L502 240Q506 297 452 297H180" />
          {/* Esquina doblada */}
          <path d="M352 26V118Q352 150 384 150H468" />
          {/* Líneas de velocidad */}
          <path d="M35 102H255M90 168H298M22 230H182M266 230H365" />
        </g>
      </svg>
      <div>
        <p className={styles.name}>Alba</p>
      </div>
    </div>
  );
}
