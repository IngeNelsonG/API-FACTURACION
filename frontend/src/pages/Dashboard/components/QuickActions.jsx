import { Link } from 'react-router-dom';
import { ChevronRightIcon, FileTextIcon, PlusIcon, SettingsIcon } from '@/components/icons';
import styles from './QuickActions.module.css';

export default function QuickActions({ onCrear }) {
  const contenido = (Icon, label) => (
    <>
      <Icon width={26} height={26} className={styles.icon} />
      <span>{label}</span>
      <ChevronRightIcon width={18} height={18} />
    </>
  );

  return (
    <section className={styles.card}>
      <h2>Acciones rápidas</h2>
      <ul>
        <li>
          <Link to="/facturas" className={styles.item}>
            {contenido(FileTextIcon, 'Ver todas mis facturas')}
          </Link>
        </li>
        <li>
          <button type="button" className={styles.item} onClick={onCrear}>
            {contenido(PlusIcon, 'Crear nueva factura')}
          </button>
        </li>
        <li>
          <Link to="/configuracion" className={styles.item}>
            {contenido(SettingsIcon, 'Configuración y modo oscuro')}
          </Link>
        </li>
      </ul>
    </section>
  );
}
