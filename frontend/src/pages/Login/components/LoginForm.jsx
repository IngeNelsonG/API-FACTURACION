import { useState } from 'react';
import { Link } from 'react-router-dom';
import Input from '@/components/ui/Input/Input';
import Button from '@/components/ui/Button/Button';
import { UserIcon, LockIcon, ArrowRightIcon, ShieldCheckIcon } from '@/components/icons';
import styles from './LoginForm.module.css';

/**
 * Formulario de inicio de sesión.
 * No sabe nada de la API: recibe onSubmit(usuario, clave) desde la página.
 */
export default function LoginForm({ onSubmit, usuarioInicial = '', aviso = '' }) {
  const [form, setForm] = useState({ usuario: usuarioInicial, clave: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const usuario = form.usuario.trim();

    // Misma validación que hace el back (400 si falta alguno)
    if (!usuario || !form.clave) {
      setError('Debe proporcionar usuario y clave');
      return;
    }

    setLoading(true);
    try {
      await onSubmit(usuario, form.clave);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <header className={styles.header}>
        <h2 className={styles.title}>Bienvenido</h2>
        <p className={styles.subtitle}>Inicia sesión para continuar</p>
      </header>

      {aviso && (
        <p className={styles.success} role="status">
          {aviso}
        </p>
      )}

      <div className={styles.fields}>
        <Input
          label="Usuario"
          name="usuario"
          icon={UserIcon}
          autoComplete="username"
          value={form.usuario}
          onChange={handleChange}
          error={Boolean(error)}
          autoFocus={!usuarioInicial}
        />
        <Input
          label="Clave"
          name="clave"
          type="password"
          icon={LockIcon}
          autoComplete="current-password"
          value={form.clave}
          onChange={handleChange}
          error={Boolean(error)}
          autoFocus={Boolean(usuarioInicial)}
        />
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <Button type="submit" loading={loading} icon={ArrowRightIcon}>
        {loading ? 'Ingresando…' : 'Iniciar sesión'}
      </Button>

      <div className={styles.divider} aria-hidden>
        <span />
      </div>

      <p className={styles.register}>
        ¿No tienes cuenta?{' '}
        <Link to="/" state={{ registro: true }}>
          Crea una aquí
        </Link>
      </p>

      <p className={styles.secure}>
        <ShieldCheckIcon width={26} height={26} />
        Tus datos están protegidos
      </p>
    </form>
  );
}
