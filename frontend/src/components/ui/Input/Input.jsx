import { forwardRef, useId, useState } from 'react';
import { EyeIcon, EyeOffIcon } from '@/components/icons';
import styles from './Input.module.css';

/**
 * Input reutilizable con ícono a la izquierda.
 * Si type="password" muestra el botón de ver/ocultar clave.
 */
const Input = forwardRef(function Input(
  { label, icon: Icon, type = 'text', error, ...rest },
  ref,
) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const isPassword = type === 'password';
  const inputType = isPassword && visible ? 'text' : type;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className={`${styles.wrapper} ${error ? styles.hasError : ''}`}>
        {Icon && <Icon className={styles.icon} />}
        <input
          id={id}
          ref={ref}
          type={inputType}
          placeholder={label}
          className={styles.input}
          aria-invalid={Boolean(error)}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Ocultar clave' : 'Mostrar clave'}
          >
            {visible ? <EyeIcon /> : <EyeOffIcon />}
          </button>
        )}
      </div>
    </div>
  );
});

export default Input;
