import { ArrowRightIcon, PlusIcon } from '@/components/icons';
import styles from './CreateInvoiceBanner.module.css';

export default function CreateInvoiceBanner({ onCreate }) {
  return (
    <section className={styles.banner}>
      <div className={styles.copy}>
        <h2>Crear nueva factura</h2>
        <p>
          Genera una factura en pocos pasos
          <br />y envíala a tus clientes.
        </p>
        <button className={styles.cta} onClick={onCreate}>
          <PlusIcon width={22} height={22} />
          Crear factura
          <ArrowRightIcon width={20} height={20} />
        </button>
      </div>

      {/* Ilustración: hoja de factura con check */}
      <svg className={styles.art} viewBox="0 0 420 260" aria-hidden>
        <circle cx="70" cy="80" r="7" fill="none" stroke="#7a1035" strokeWidth="3.5" />
        <circle cx="12" cy="200" r="4" fill="#c4577f" />
        <circle cx="400" cy="210" r="3" fill="#9fd3f3" />
        <ellipse cx="260" cy="150" rx="150" ry="95" fill="#cfe9f9" opacity="0.55" />
        <g transform="rotate(9 255 130)">
          <rect x="165" y="20" width="175" height="210" rx="16" fill="#fff" />
          <rect x="165" y="20" width="175" height="210" rx="16" fill="none" stroke="#e5e7ef" strokeWidth="2" />
          <text x="185" y="62" fontFamily="Poppins, sans-serif" fontWeight="700" fontSize="22" fill="#13183a">
            FACTURA
          </text>
          <rect x="185" y="76" width="130" height="8" rx="4" fill="#7cc8f2" />
          {[100, 118, 136, 154, 172, 190].map((y, i) => (
            <g key={y} fill="#e3e6f0">
              <rect x="185" y={y} width={i % 2 ? 60 : 80} height="7" rx="3.5" />
              <rect x={i % 2 ? 260 : 280} y={y} width={i % 2 ? 55 : 35} height="7" rx="3.5" />
            </g>
          ))}
        </g>
        <path d="M335 18 l10 -14 M350 32 l16 -6 M346 44 l14 4" stroke="#7a1035" strokeWidth="4" strokeLinecap="round" />
        <circle cx="330" cy="185" r="38" fill="#7a1035" />
        <path d="M313 186l12 12 22-24" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </section>
  );
}
