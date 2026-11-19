import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { PlusIcon } from '@/components/icons';
import CreateInvoiceModal from '@/components/invoices/CreateInvoiceModal';
import Pagination from '@/components/ui/Pagination/Pagination';
import Toast from '@/components/ui/Toast/Toast';
import { useAuth } from '@/hooks/useAuth';
import { useFacturas } from '@/hooks/useFacturas';
import { getPersonas } from '@/api/personasService';
import { parseFechaSqlite } from '@/utils/format';
import FacturasFilters, { FILTROS_VACIOS } from './components/FacturasFilters';
import FacturasTable from './components/FacturasTable';
import InvoiceDetailModal from './components/InvoiceDetailModal';
import styles from './FacturasPage.module.css';

const POR_PAGINA = 7;

// Fecha local de la factura en "YYYY-MM-DD" para compararla con los <input type="date">
const fechaLocal = (f) => parseFechaSqlite(f.fecha_emision)?.toLocaleDateString('en-CA') ?? '';

export default function FacturasPage() {
  const { session } = useAuth();
  const { busqueda = '' } = useOutletContext() ?? {};
  const { facturas, loading, error, aviso, setAviso, recargar, pagar, anular, enviarCorreo, descargarPdf } =
    useFacturas();
  const esCliente = session?.rol === 'cliente';

  const [personas, setPersonas] = useState([]);
  const [borrador, setBorrador] = useState(FILTROS_VACIOS); // lo que el usuario está editando
  const [filtros, setFiltros] = useState(FILTROS_VACIOS); // lo que se aplicó con "Buscar"
  const [pagina, setPagina] = useState(1);
  const [detalle, setDetalle] = useState(null);
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (esCliente) {
      setPersonas([]);
      return;
    }
    getPersonas().then(setPersonas).catch(() => setPersonas([]));
  }, [esCliente]);

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return facturas.filter((f) => {
      const dia = fechaLocal(f);
      if (filtros.desde && dia < filtros.desde) return false;
      if (filtros.hasta && dia > filtros.hasta) return false;
      if (filtros.estado && f.estado !== filtros.estado) return false;
      if (filtros.personaId && String(f.persona_id) !== filtros.personaId) return false;
      if (q) {
        const texto = [f.numero, f.cliente_nombre, f.cliente_cedula, f.concepto, fechaLocal(f)]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!texto.includes(q)) return false;
      }
      return true;
    });
  }, [facturas, filtros, busqueda]);

  // Volver a la página 1 cuando cambian los resultados
  useEffect(() => setPagina(1), [filtros, busqueda]);

  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / POR_PAGINA));
  const paginaSegura = Math.min(pagina, totalPaginas);
  const inicio = (paginaSegura - 1) * POR_PAGINA;
  const visibles = filtradas.slice(inicio, inicio + POR_PAGINA);

  const hayFiltros = Object.values(filtros).some(Boolean) || busqueda.trim();

  const limpiar = () => {
    setBorrador(FILTROS_VACIOS);
    setFiltros(FILTROS_VACIOS);
  };

  const handleCreada = (factura) => {
    setCreando(false);
    setAviso({ tipo: 'ok', texto: `Factura ${factura.numero} emitida exitosamente` });
    recargar();
  };

  // El detalle muestra la versión más reciente de la factura (tras pagar / enviar)
  const detalleActual = detalle ? facturas.find((f) => f.id === detalle.id) ?? detalle : null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Mis Facturas</h1>
          <p>Consulta y gestiona todas tus facturas en un solo lugar</p>
        </div>
        <button className={styles.newBtn} onClick={() => setCreando(true)}>
          <PlusIcon width={22} height={22} />
          Nueva Factura
        </button>
      </header>

      <FacturasFilters
        valores={borrador}
        personas={personas}
        mostrarCliente={!esCliente}
        onChange={setBorrador}
        onBuscar={() => setFiltros(borrador)}
        onLimpiar={limpiar}
      />

      <section className={styles.card}>
        <FacturasTable
          facturas={visibles}
          loading={loading}
          error={error}
          vacio={hayFiltros ? 'No hay facturas que coincidan con los filtros' : 'Aún no has emitido facturas'}
          onVer={setDetalle}
          onDescargar={descargarPdf}
          onEnviar={enviarCorreo}
          onPagar={pagar}
          onAnular={anular}
        />
        {!loading && !error && (
          <Pagination
            pagina={paginaSegura}
            totalPaginas={totalPaginas}
            total={filtradas.length}
            desde={filtradas.length ? inicio + 1 : 0}
            hasta={inicio + visibles.length}
            etiqueta="facturas"
            onChange={setPagina}
          />
        )}
      </section>

      <InvoiceDetailModal
        factura={detalleActual}
        onClose={() => setDetalle(null)}
        onEnviar={enviarCorreo}
        onDescargar={descargarPdf}
      />
      <CreateInvoiceModal open={creando} onClose={() => setCreando(false)} onCreated={handleCreada} />
      <Toast aviso={aviso} />
    </div>
  );
}
