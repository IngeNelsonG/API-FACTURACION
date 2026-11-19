import { useMemo } from 'react';
import { useFacturas } from '@/hooks/useFacturas';
import { calcularEstadisticas } from '@/utils/facturaStats';

/** Facturas + estadísticas para las tarjetas del dashboard */
export function useDashboardData() {
  const data = useFacturas();
  const stats = useMemo(() => calcularEstadisticas(data.facturas), [data.facturas]);
  return { ...data, stats };
}
