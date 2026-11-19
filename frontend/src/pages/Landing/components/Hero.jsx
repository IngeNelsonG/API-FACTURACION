import { Link } from 'react-router-dom';
import { ArrowRightIcon, ChevronDownIcon } from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import heroImg from '@/assets/hero-alcancia.jpg';
import styles from './Hero.module.css';

const irA = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

export default function Hero() {
  const { isAuthenticated } = useAuth();

  return (
    <section className={styles.hero}>
      <HeroArt />

      <div className={styles.content}>
        <h1 className={styles.title}>
          Facturación electrónica DIAN
          <span className={styles.accent}>simple y sin complicaciones</span>
        </h1>
        <p className={styles.subtitle}>
          Bienvenido a Alba, tu aliado en la gestión{' '}
          <br />
          de facturas y cuentas.
        </p>

        <div className={styles.actions}>
          <Link to={isAuthenticated ? '/dashboard' : '/login'} className={styles.primary}>
            {isAuthenticated ? 'Ir a mi panel' : 'Iniciar Sesión'}
            <ArrowRightIcon width={20} height={20} />
          </Link>
          <button type="button" className={styles.secondary} onClick={() => irA('que-hace')}>
            Conocer más <ChevronDownIcon width={20} height={20} />
          </button>
        </div>
      </div>

      <button type="button" className={styles.scrollHint} onClick={() => irA('que-hace')}>
        <ChevronDownIcon width={30} height={30} className={styles.bounce} />
        Desliza para más información
      </button>
    </section>
  );
}

/** Fondo: foto de la alcancía desvanecida + manchas de color encima */
function HeroArt() {
  return (
    <div className={styles.art} aria-hidden>
      <img src={heroImg} alt="" className={styles.photo} />
      <span className={styles.veil} />
      <span className={`${styles.blob} ${styles.blobBlue}`} />
      <span className={`${styles.blob} ${styles.blobPink}`} />
      <span className={`${styles.blob} ${styles.blobBlueSm}`} />
      <span className={`${styles.wave} ${styles.waveRight}`} />
    </div>
  );
}
