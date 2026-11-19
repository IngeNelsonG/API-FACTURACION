import styles from './Toast.module.css';

/** Aviso flotante abajo a la derecha. aviso = { tipo: 'ok' | 'error', texto } */
export default function Toast({ aviso }) {
  if (!aviso) return null;
  return (
    <div className={`${styles.toast} ${aviso.tipo === 'error' ? styles.error : ''}`} role="status">
      {aviso.texto}
    </div>
  );
}
