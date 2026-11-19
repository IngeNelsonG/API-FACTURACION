import { Link } from 'react-router-dom';
import { ArrowRightIcon, SendIcon } from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import styles from './CtaBanner.module.css';

export default function CtaBanner({ onRegistro }) {
  const { isAuthenticated } = useAuth();

  return (
    <section className={styles.wrap}>
      <div className={styles.banner}>
        <SendIcon width={56} height={56} className={styles.icon} />
        <div className={styles.copy}>
          <h2>¿Listo para gestionar tus facturas y clientes?</h2>
          <p>Accede a Alba y lleva tu negocio al siguiente nivel.</p>
        </div>
        <div className={styles.buttons}>
          {!isAuthenticated && (
            <button type="button" className={styles.ghost} onClick={onRegistro}>
              Crear cuenta
            </button>
          )}
          <Link to={isAuthenticated ? '/dashboard' : '/login'} className={styles.button}>
            {isAuthenticated ? 'Ir a mi panel' : 'Iniciar Sesión en Alba'}
            <ArrowRightIcon width={18} height={18} />
          </Link>
        </div>
      </div>
    </section>
  );
}
