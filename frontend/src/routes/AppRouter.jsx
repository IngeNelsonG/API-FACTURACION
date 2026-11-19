import { BrowserRouter, Route, Routes } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import PublicRoute from './PublicRoute';
import AppLayout from '@/components/layout/AppLayout';
import LandingPage from '@/pages/Landing/LandingPage';
import LoginPage from '@/pages/Login/LoginPage';
import DashboardPage from '@/pages/Dashboard/DashboardPage';
import FacturasPage from '@/pages/Facturas/FacturasPage';
import ConfiguracionPage from '@/pages/Configuracion/ConfiguracionPage';
import NotFoundPage from '@/pages/NotFound/NotFoundPage';

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Index público: visible con o sin sesión */}
        <Route path="/" element={<LandingPage />} />

        <Route element={<PublicRoute />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>

        {/* Rutas privadas: todas comparten sidebar + topbar */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/facturas" element={<FacturasPage />} />
            <Route path="/configuracion" element={<ConfiguracionPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
