import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from '@/components/ui/Modal/Modal';
import Button from '@/components/ui/Button/Button';
import { ArrowRightIcon } from '@/components/icons';
import { useAuth } from '@/hooks/useAuth';
import { getPersonas } from '@/api/personasService';
import { crearFactura } from '@/api/facturasService';
import { formatCOP } from '@/utils/format';
import { liquidar } from '@/utils/impuestos';
import styles from './CreateInvoiceModal.module.css';

const VACIO = { persona_id: '', concepto: '', subtotal: '' };

export default function CreateInvoiceModal({ open, onClose, onCreated }) {
  const { session } = useAuth();
  const esCliente = session?.rol === 'cliente';
  const [personas, setPersonas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!open) return;
    const personaPropia = esCliente && session?.persona_id ? String(session.persona_id) : '';
    setForm({ ...VACIO, persona_id: personaPropia });
    setError('');
    setCargando(true);
    getPersonas()
      .then((lista) => {
        if (esCliente && session?.persona_id) {
          setPersonas(lista.filter((p) => p.id === session.persona_id));
        } else {
          setPersonas(lista);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false));
  }, [open, esCliente, session?.persona_id]);

  const calc = useMemo(() => liquidar(form.subtotal), [form.subtotal]);

  const handleChange = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.persona_id || !form.concepto.trim() || !form.subtotal) {
      setError('Debe enviar cliente, concepto y subtotal');
      return;
    }
    if (Number(form.subtotal) <= 0) {
      setError('El subtotal debe ser un valor numérico positivo');
      return;
    }
    setEnviando(true);
    try {
      const res = await crearFactura({
        persona_id: Number(form.persona_id),
        concepto: form.concepto.trim(),
        subtotal: Number(form.subtotal),
      });
      onCreated(res.factura);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const sinClientes = !cargando && personas.length === 0;

  return (
    <Modal open={open} title="Nueva factura electrónica" onClose={onClose}>
      {sinClientes && !error ? (
        <div className={styles.empty}>
          <p>Aún no hay clientes registrados.</p>
          <p>Los clientes se registran al crear su cuenta desde la página de inicio.</p>
          <Link to="/" state={{ registro: true }} className={styles.link} onClick={onClose}>
            Ir al registro
          </Link>
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <label className={styles.field}>
            <span>Cliente</span>
            <select
              name="persona_id"
              value={form.persona_id}
              onChange={handleChange}
              disabled={cargando || esCliente}
            >
              <option value="">{cargando ? 'Cargando clientes…' : 'Selecciona un cliente'}</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} · CC {p.cedula}
                </option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span>Concepto</span>
            <input
              name="concepto"
              placeholder="Ej: Desarrollo de software a la medida"
              value={form.concepto}
              onChange={handleChange}
              maxLength={200}
            />
          </label>

          <label className={styles.field}>
            <span>Subtotal (COP)</span>
            <input
              name="subtotal"
              type="number"
              min="1"
              step="1"
              inputMode="numeric"
              placeholder="0"
              value={form.subtotal}
              onChange={handleChange}
            />
          </label>

          <dl className={styles.summary}>
            <div>
              <dt>Subtotal</dt>
              <dd>{formatCOP(calc.base)}</dd>
            </div>
            <div>
              <dt>IVA (19%)</dt>
              <dd>{formatCOP(calc.iva)}</dd>
            </div>
            <div className={styles.grand}>
              <dt>Total</dt>
              <dd>{formatCOP(calc.total)}</dd>
            </div>
            <div className={styles.note}>
              <dt>4x1000 que retendrá el banco al pagar*</dt>
              <dd>{formatCOP(calc.gmf)}</dd>
            </div>
          </dl>
          <p className={styles.footnote}>
            * Informativo: el 4x1000 lo cobra el banco sobre el pago, no se suma a la factura.
          </p>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <Button type="submit" loading={enviando} icon={ArrowRightIcon}>
            {enviando ? 'Emitiendo…' : 'Emitir factura'}
          </Button>
        </form>
      )}
    </Modal>
  );
}
