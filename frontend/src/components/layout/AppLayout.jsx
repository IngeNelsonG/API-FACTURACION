import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useTheme } from '@/hooks/useTheme';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import styles from './AppLayout.module.css';

/**
 * Esqueleto de todas las vistas privadas: sidebar + topbar + contenido.
 * La búsqueda vive aquí y se comparte con la página vía useOutletContext().
 */
export default function AppLayout() {
  const [busqueda, setBusqueda] = useState('');
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { tema } = useTheme();

  // El tema se aplica al <html> (así también lo heredan los modales, que van en un portal)
  // y se quita al salir del panel para que el index y el login sigan claros.
  useEffect(() => {
    document.documentElement.dataset.theme = tema;
    return () => {
      delete document.documentElement.dataset.theme;
    };
  }, [tema]);

  return (
    <div className={styles.shell}>
      <Sidebar open={menuAbierto} onClose={() => setMenuAbierto(false)} />

      <div className={styles.main}>
        <Topbar
          busqueda={busqueda}
          onBusqueda={setBusqueda}
          onMenu={() => setMenuAbierto(true)}
        />
        <div className={styles.content}>
          <Outlet context={{ busqueda }} />
        </div>
      </div>
    </div>
  );
}
