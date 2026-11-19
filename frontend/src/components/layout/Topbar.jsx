import { BellIcon, MenuIcon, SearchIcon } from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import { iniciales } from '@/utils/format';
import styles from './Topbar.module.css';

export default function Topbar({ busqueda, onBusqueda, onMenu }) {
  const { session } = useAuth();

  return (
    <header className={styles.topbar}>
      <button className={styles.menu} onClick={onMenu} aria-label="Abrir menú">
        <MenuIcon />
      </button>

      <label className={styles.search}>
        <SearchIcon width={22} height={22} />
        <span className="sr-only">Buscar</span>
        <input
          type="search"
          placeholder="Buscar facturas, clientes o números..."
          value={busqueda}
          onChange={(e) => onBusqueda(e.target.value)}
        />
      </label>

      <div className={styles.actions}>
        <button className={styles.bell} aria-label="Notificaciones">
          <BellIcon width={28} height={28} />
          <span className={styles.badge} />
        </button>
        <span className={styles.avatar} title={session.usuario}>
          {iniciales(session.nombre || session.usuario)}
        </span>
      </div>
    </header>
  );
}
