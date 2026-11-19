import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { capitalizar } from '@/utils/format';
import styles from './ConfiguracionPage.module.css';

const TEMAS = [
  { id: 'claro', titulo: 'Claro', descripcion: 'Fondo blanco, ideal con buena luz' },
  { id: 'oscuro', titulo: 'Oscuro', descripcion: 'Descansa la vista de noche' },
];

export default function ConfiguracionPage() {
  const { tema, oscuro, setTema, alternar } = useTheme();
  const { session } = useAuth();
  const expira = new Date(session.expira).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>Configuración</h1>
        <p>Personaliza cómo se ve tu panel de Alba</p>
      </header>

      <section className={styles.card}>
        <div className={styles.row}>
          <div>
            <h2>Modo oscuro</h2>
            <p>Se aplica de una vez al Inicio, a Mis Facturas y a esta página. Se guarda en este navegador.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={oscuro}
            aria-label="Activar modo oscuro"
            className={`${styles.switch} ${oscuro ? styles.on : ''}`}
            onClick={alternar}
          >
            <span className={styles.knob} />
          </button>
        </div>

        <div className={styles.temas} role="radiogroup" aria-label="Tema">
          {TEMAS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={tema === t.id}
              className={`${styles.tema} ${tema === t.id ? styles.activo : ''}`}
              onClick={() => setTema(t.id)}
            >
              <span className={`${styles.preview} ${styles[t.id]}`} aria-hidden>
                <span className={styles.pSide} />
                <span className={styles.pMain}>
                  <span className={styles.pBar} />
                  <span className={styles.pCards}>
                    <span />
                    <span className={styles.pUrgent} />
                    <span />
                  </span>
                  <span className={styles.pTable} />
                </span>
              </span>
              <strong>{t.titulo}</strong>
              <small>{t.descripcion}</small>
            </button>
          ))}
        </div>
      </section>

      <section className={styles.card}>
        <h2>Mi cuenta</h2>
        <dl className={styles.cuenta}>
          <div>
            <dt>Usuario</dt>
            <dd>{session.usuario}</dd>
          </div>
          {session.nombre && (
            <div>
              <dt>Nombre</dt>
              <dd>{session.nombre}</dd>
            </div>
          )}
          <div>
            <dt>Rol</dt>
            <dd>{capitalizar(session.rol)}</dd>
          </div>
          <div>
            <dt>La sesión vence a las</dt>
            <dd>{expira}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
