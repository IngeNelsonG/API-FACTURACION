import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { XIcon } from '@/components/icons';
import styles from './Modal.module.css';

/** Modal genérico: cierra con Esc, clic afuera o la X */
export default function Modal({ open, title, onClose, children }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className={styles.backdrop} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <header className={styles.header}>
          <h2 id="modal-title">{title}</h2>
          <button type="button" className={styles.close} onClick={onClose} aria-label="Cerrar">
            <XIcon width={20} height={20} />
          </button>
        </header>
        {children}
      </div>
    </div>,
    document.body,
  );
}
