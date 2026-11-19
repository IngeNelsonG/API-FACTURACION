import { useCallback, useEffect, useState } from 'react';
import {
  getFacturas,
  pagarFactura,
  anularFactura,
  enviarFacturaCorreo,
  descargarPdfFactura,
} from '@/api/facturasService';

/**
 * Estado compartido de facturas (Dashboard y Facturas):
 * carga la lista y expone acciones con aviso (toast) de resultado.
 */
export function useFacturas() {
  const [facturas, setFacturas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState(null); // { tipo: 'ok' | 'error', texto }

  const recargar = useCallback(async () => {
    setError('');
    try {
      setFacturas(await getFacturas());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  // El aviso desaparece solo a los 4 s
  useEffect(() => {
    if (!aviso) return undefined;
    const t = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(t);
  }, [aviso]);

  const ejecutar = useCallback(
    async (accion, factura, { recargarDespues = true } = {}) => {
      try {
        const res = await accion(factura.id);
        setAviso({ tipo: 'ok', texto: res.mensaje });
        if (recargarDespues) await recargar();
      } catch (e) {
        setAviso({ tipo: 'error', texto: e.message });
      }
    },
    [recargar],
  );

  const pagar = useCallback((f) => ejecutar(pagarFactura, f), [ejecutar]);

  const anular = useCallback(
    (f) => {
      if (window.confirm(`¿Seguro que deseas anular la factura ${f.numero}?`)) {
        ejecutar(anularFactura, f);
      }
    },
    [ejecutar],
  );

  const enviarCorreo = useCallback((f) => ejecutar(enviarFacturaCorreo, f), [ejecutar]);

  const descargarPdf = useCallback(async (f) => {
    try {
      await descargarPdfFactura(f);
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.message });
    }
  }, []);

  return { facturas, loading, error, aviso, setAviso, recargar, pagar, anular, enviarCorreo, descargarPdf };
}
