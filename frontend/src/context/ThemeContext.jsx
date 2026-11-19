import { createContext, useCallback, useMemo, useState } from 'react';

const STORAGE_KEY = 'alba_tema';

export const ThemeContext = createContext(null);

function temaGuardado() {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'oscuro' ? 'oscuro' : 'claro';
  } catch {
    return 'claro';
  }
}

/**
 * Tema del panel ("claro" | "oscuro"). Se guarda en el navegador.
 * Quien lo aplica al <html> es AppLayout, así el index y el login siempre quedan claros.
 */
export function ThemeProvider({ children }) {
  const [tema, setTemaState] = useState(temaGuardado);

  const setTema = useCallback((nuevo) => {
    setTemaState(nuevo);
    try {
      localStorage.setItem(STORAGE_KEY, nuevo);
    } catch {
      /* sin almacenamiento: el tema dura solo esta sesión */
    }
  }, []);

  const value = useMemo(
    () => ({
      tema,
      oscuro: tema === 'oscuro',
      setTema,
      alternar: () => setTema(tema === 'oscuro' ? 'claro' : 'oscuro'),
    }),
    [tema, setTema],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
