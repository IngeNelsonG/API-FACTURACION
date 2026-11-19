import { CalendarIcon, RefreshIcon, SearchIcon } from '@/components/icons';
import styles from './FacturasFilters.module.css';

export const FILTROS_VACIOS = { desde: '', hasta: '', estado: '', personaId: '' };

/** Barra de filtros. Los cambios quedan en "borrador" hasta pulsar Buscar. */
export default function FacturasFilters({ valores, personas, onChange, onBuscar, onLimpiar }) {
  const set = (campo) => (e) => onChange({ ...valores, [campo]: e.target.value });

  return (
    <form
      className={styles.bar}
      onSubmit={(e) => {
        e.preventDefault();
        onBuscar();
      }}
    >
      <div className={`${styles.control} ${styles.dates}`}>
        <CalendarIcon width={20} height={20} />
        <label className="sr-only" htmlFor="f-desde">Desde</label>
        <input id="f-desde" type="date" value={valores.desde} max={valores.hasta || undefined} onChange={set('desde')} />
        <span aria-hidden>–</span>
        <label className="sr-only" htmlFor="f-hasta">Hasta</label>
        <input id="f-hasta" type="date" value={valores.hasta} min={valores.desde || undefined} onChange={set('hasta')} />
      </div>

      <label className="sr-only" htmlFor="f-estado">Estado</label>
      <select id="f-estado" className={styles.control} value={valores.estado} onChange={set('estado')}>
        <option value="">Todos los estados</option>
        <option value="PAGADA">Pagada</option>
        <option value="EMITIDA">Pendiente</option>
        <option value="ANULADA">Anulada</option>
      </select>

      <label className="sr-only" htmlFor="f-cliente">Cliente</label>
      <select id="f-cliente" className={styles.control} value={valores.personaId} onChange={set('personaId')}>
        <option value="">Todos los clientes</option>
        {personas.map((p) => (
          <option key={p.id} value={p.id}>
            {p.nombre}
          </option>
        ))}
      </select>

      <div className={styles.buttons}>
        <button type="button" className={styles.clear} onClick={onLimpiar}>
          <RefreshIcon width={18} height={18} />
          Limpiar filtros
        </button>
        <button type="submit" className={styles.search}>
          <SearchIcon width={18} height={18} />
          Buscar
        </button>
      </div>
    </form>
  );
}
