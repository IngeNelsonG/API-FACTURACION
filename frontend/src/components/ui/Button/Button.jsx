import styles from './Button.module.css';

/** Botón primario reutilizable con estado de carga */
export default function Button({ children, loading = false, icon: Icon, className = '', ...rest }) {
  return (
    <button
      className={`${styles.button} ${className}`}
      disabled={loading || rest.disabled}
      aria-busy={loading}
      {...rest}
    >
      {loading ? <span className={styles.spinner} aria-hidden /> : null}
      <span>{children}</span>
      {!loading && Icon ? <Icon className={styles.icon} /> : null}
    </button>
  );
}
