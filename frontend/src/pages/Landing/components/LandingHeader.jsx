import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Logo from '@/components/brand/Logo';
import { LockIcon, ArrowRightIcon } from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import styles from './LandingHeader.module.css';

export default function LandingHeader({ onRegistro }) {
  const { isAuthenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  // Al bajar, el header gana fondo blanco translúcido
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={`${styles.header} ${scrolled ? styles.scrolled : ''}`}>
      <Link to="/" aria-label="Alba, inicio" className={styles.brand}>
        <Logo variant="brand" size="md" showTagline={false} />
      </Link>

      {isAuthenticated ? (
        <Link to="/dashboard" className={styles.cta}>
          Ir a mi panel <ArrowRightIcon width={18} height={18} />
        </Link>
      ) : (
        <div className={styles.actions}>
          <button type="button" className={styles.secondary} onClick={onRegistro}>
            Crear cuenta
          </button>
          <Link to="/login" className={styles.cta}>
            <LockIcon width={20} height={20} /> Iniciar Sesión
          </Link>
        </div>
      )}
    </header>
  );
}
