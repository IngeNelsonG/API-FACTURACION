import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import Logo from '@/components/brand/Logo';
import {
  HomeIcon,
  FileTextIcon,
  SettingsIcon,
  ChevronDownIcon,
  LogoutIcon,
} from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import { capitalizar, iniciales } from '@/utils/format';
import styles from './Sidebar.module.css';

const NAV = [
  { to: '/dashboard', label: 'Inicio', Icon: HomeIcon },
  { to: '/facturas', label: 'Facturas', Icon: FileTextIcon },
  { to: '/configuracion', label: 'Configuración', Icon: SettingsIcon },
];

export default function Sidebar({ open, onClose }) {
  const { session, logout } = useAuth();
  const [cuentaAbierta, setCuentaAbierta] = useState(false);

  return (
    <>
      <div
        className={`${styles.overlay} ${open ? styles.overlayVisible : ''}`}
        onClick={onClose}
        aria-hidden
      />
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`}>
        <div className={styles.brand}>
          <Logo variant="dark" size="sm" showTagline={false} />
        </div>

        <nav className={styles.nav}>
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            >
              <Icon width={24} height={24} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className={styles.account}>
          {cuentaAbierta && (
            <button className={styles.logout} onClick={logout}>
              <LogoutIcon width={18} height={18} />
              Cerrar sesión
            </button>
          )}
          <button
            className={styles.user}
            onClick={() => setCuentaAbierta((v) => !v)}
            aria-expanded={cuentaAbierta}
          >
            <span className={styles.avatar}>{iniciales(session.nombre || session.usuario)}</span>
            <span className={styles.userText}>
              <strong>{session.nombre || capitalizar(session.usuario)}</strong>
              <small>Mi cuenta · {session.rol}</small>
            </span>
            <ChevronDownIcon
              width={18}
              height={18}
              className={`${styles.chevron} ${cuentaAbierta ? styles.chevronUp : ''}`}
            />
          </button>
        </div>
      </aside>
    </>
  );
}
