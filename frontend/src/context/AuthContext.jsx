import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import * as authService from '@/api/authService';
import { saveSession, loadSession, clearSession } from '@/utils/storage';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => loadSession());

  const login = useCallback(async (usuario, clave) => {
    const data = await authService.login(usuario, clave);
    const nueva = {
      token: data.token,
      usuario: data.usuario,
      nombre: data.nombre || null,
      rol: data.rol,
      expira: data.expira,
    };
    saveSession(nueva);
    setSession(nueva);
    return nueva;
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  // Cierra la sesión automáticamente cuando el JWT (2 h) expira
  useEffect(() => {
    if (!session?.expira) return undefined;
    const ms = new Date(session.expira).getTime() - Date.now();
    if (ms <= 0) {
      logout();
      return undefined;
    }
    const timer = setTimeout(logout, ms);
    return () => clearTimeout(timer);
  }, [session, logout]);

  const value = useMemo(
    () => ({ session, isAuthenticated: Boolean(session), login, logout }),
    [session, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
