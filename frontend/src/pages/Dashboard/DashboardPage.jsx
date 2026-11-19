import { useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { capitalizar } from '@/utils/format';
import { ClockIcon, FileTextIcon, CheckIcon, XIcon } from '@/components/icons';
import { useDashboardData } from './hooks/useDashboardData';
import StatCard from './components/StatCard';
import CreateInvoiceBanner from './components/CreateInvoiceBanner';
import CreateInvoiceModal from '@/components/invoices/CreateInvoiceModal';
import RecentActivity from './components/RecentActivity';
import QuickActions from './components/QuickActions';
import SecurityCard from './components/SecurityCard';
import styles from './DashboardPage.module.css';

const MAX_RECIENTES = 5;

export default function DashboardPage() {
  const { session } = useAuth();
  const { busqueda = '' } = useOutletContext() ?? {};
  const { facturas, stats, loading, error, aviso, setAviso, recargar, pagar, anular, descargarPdf } =
    useDashboardData();
  const [modalAbierto, setModalAbierto] = useState(false);

  // Con búsqueda: filtra todas; sin búsqueda: las 5 más recientes
  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return facturas.slice(0, MAX_RECIENTES);
    return facturas.filter((f) =>
      [f.numero, f.cliente_nombre, f.cliente_cedula, f.concepto]
        .filter(Boolean)
        .some((v) => v.toLowerCase().includes(q)),
    );
  }, [facturas, busqueda]);

  const handleCreada = (factura) => {
    setModalAbierto(false);
    setAviso({ tipo: 'ok', texto: `Factura ${factura.numero} emitida exitosamente` });
    recargar();
  };

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <h1>
            Hola, {capitalizar(session.nombre?.split(' ')[0] || session.usuario)} <span aria-hidden>👋</span>
          </h1>
          <p>Gestiona tus facturas de forma fácil y segura</p>
        </div>
        <p className={styles.script} aria-hidden>
          Facturación inteligente
          <br />
          para hacer crecer tu negocio
        </p>
      </header>

      {/* Orden del ciclo de vida: azul · vinotinto · azul · gris */}
      <section className={styles.stats} aria-label="Resumen de facturas">
        <StatCard
          variant="blue"
          Icon={FileTextIcon}
          label="Facturas Emitidas"
          loading={loading}
          {...stats.emitidas}
        />
        <StatCard
          variant="urgent"
          Icon={ClockIcon}
          label="Pendientes de Pago"
          loading={loading}
          {...stats.pendientes}
        />
        <StatCard
          variant="blue"
          Icon={CheckIcon}
          label="Facturas Pagadas"
          loading={loading}
          {...stats.pagadas}
        />
        <StatCard
          variant="gray"
          Icon={XIcon}
          label="Anuladas"
          loading={loading}
          {...stats.anuladas}
        />
      </section>

      <div className={styles.grid}>
        <div className={styles.mainCol}>
          <CreateInvoiceBanner onCreate={() => setModalAbierto(true)} />
          <RecentActivity
            facturas={visibles}
            loading={loading}
            error={error}
            busqueda={busqueda}
            onPagar={pagar}
            onAnular={anular}
            onDescargar={descargarPdf}
          />
        </div>
        <aside className={styles.sideCol}>
          <QuickActions onCrear={() => setModalAbierto(true)} />
          <SecurityCard />
        </aside>
      </div>

      <CreateInvoiceModal
        open={modalAbierto}
        onClose={() => setModalAbierto(false)}
        onCreated={handleCreada}
      />

      {aviso && (
        <div className={`${styles.toast} ${aviso.tipo === 'error' ? styles.toastError : ''}`} role="status">
          {aviso.texto}
        </div>
      )}
    </div>
  );
}
