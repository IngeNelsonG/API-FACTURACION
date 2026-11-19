import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import BrandPanel from './components/BrandPanel';
import SpaceScene from './components/SpaceScene';
import LoginForm from './components/LoginForm';
import styles from './LoginPage.module.css';

/**
 * Página = orquesta. Compone las piezas visuales y conecta el formulario
 * con el contexto de autenticación y la navegación.
 */
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destino = location.state?.from?.pathname || '/dashboard';
  const registrado = location.state?.registrado || '';

  const handleLogin = async (usuario, clave) => {
    await login(usuario, clave); // si falla, LoginForm muestra el error
    navigate(destino, { replace: true });
  };

  return (
    <main className={styles.page}>
      <SpaceScene />

      <section className={styles.brand}>
        <BrandPanel />
      </section>

      <section className={styles.formArea}>
        <LoginForm
          onSubmit={handleLogin}
          usuarioInicial={registrado}
          aviso={registrado ? `¡Cuenta creada! Inicia sesión como ${registrado}.` : ''}
        />
      </section>
    </main>
  );
}
