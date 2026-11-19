import { useEffect, useState } from 'react';
import Modal from '@/components/ui/Modal/Modal';
import Button from '@/components/ui/Button/Button';
import { ArrowRightIcon } from '@/components/icons';
import { registrar } from '@/api/authService';
import styles from './RegisterModal.module.css';

const VACIO = {
  nombre: '',
  cedula: '',
  rut: '',
  telefono: '',
  correo: '',
  direccion: '',
  usuario: '',
  clave: '',
  confirmar: '',
};

const PATRON_USUARIO = /^[A-Za-z0-9._-]{3,30}$/;

/** Mismas reglas que valida POST /registro en el back */
function validar(f) {
  const obligatorios = { nombre: 'nombre', cedula: 'cédula', rut: 'RUT', correo: 'correo', direccion: 'dirección' };
  for (const [campo, etiqueta] of Object.entries(obligatorios)) {
    if (!f[campo].trim()) return `El campo ${etiqueta} es obligatorio`;
  }
  if (!/^\S+@\S+\.\S+$/.test(f.correo.trim())) return 'El correo electrónico no es válido';
  if (!PATRON_USUARIO.test(f.usuario.trim())) {
    return 'El usuario debe tener entre 3 y 30 caracteres (letras, números, punto, guion o guion bajo)';
  }
  if (f.clave.length < 6) return 'La clave debe tener al menos 6 caracteres';
  if (f.clave !== f.confirmar) return 'Las claves no coinciden';
  return '';
}

/**
 * Registro público: crea la cuenta (usuario + clave) y registra a la persona como cliente.
 * Al terminar llama onRegistrado(usuario) para llevarlo al login.
 */
export default function RegisterModal({ open, onClose, onRegistrado }) {
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(VACIO);
      setError('');
    }
  }, [open]);

  const set = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const problema = validar(form);
    if (problema) {
      setError(problema);
      return;
    }
    setEnviando(true);
    try {
      const { confirmar, ...datos } = form;
      const limpio = Object.fromEntries(
        Object.entries(datos).map(([k, v]) => [k, k === 'clave' ? v : v.trim()]),
      );
      await registrar(limpio);
      onRegistrado(limpio.usuario);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const campo = (name, label, props = {}) => (
    <label className={`${styles.field} ${props.full ? styles.full : ''}`}>
      <span>{label}</span>
      <input name={name} value={form[name]} onChange={set} {...props} full={undefined} />
    </label>
  );

  return (
    <Modal open={open} title="Crear cuenta en Alba" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <p className={styles.intro}>
          Con tu cuenta podrás iniciar sesión y quedarás registrado como cliente para recibir tus
          facturas.
        </p>

        <fieldset className={styles.group}>
          <legend>Datos personales</legend>
          {campo('nombre', 'Nombre completo', { autoComplete: 'name', full: true })}
          {campo('cedula', 'Cédula', { inputMode: 'numeric' })}
          {campo('rut', 'RUT', { placeholder: 'Ej: 1020304050-1' })}
          {campo('telefono', 'Teléfono (opcional)', { inputMode: 'tel', autoComplete: 'tel' })}
          {campo('correo', 'Correo electrónico', { type: 'email', autoComplete: 'email' })}
          {campo('direccion', 'Dirección', { autoComplete: 'street-address', full: true })}
        </fieldset>

        <fieldset className={styles.group}>
          <legend>Datos de acceso</legend>
          {campo('usuario', 'Usuario', { autoComplete: 'username', full: true, placeholder: 'Ej: maria.lopez' })}
          {campo('clave', 'Clave', { type: 'password', autoComplete: 'new-password', placeholder: 'Mínimo 6 caracteres' })}
          {campo('confirmar', 'Confirmar clave', { type: 'password', autoComplete: 'new-password' })}
        </fieldset>

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        <Button type="submit" loading={enviando} icon={ArrowRightIcon}>
          {enviando ? 'Creando cuenta…' : 'Crear cuenta'}
        </Button>
      </form>
    </Modal>
  );
}
