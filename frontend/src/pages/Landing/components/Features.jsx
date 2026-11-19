import { CalculatorIcon, PdfFileIcon, ShieldCheckIcon } from '@/components/icons';
import SectionTitle from './SectionTitle';
import styles from './Features.module.css';

const FEATURES = [
  {
    Icon: CalculatorIcon,
    titulo: 'Cálculo Tributario Automático',
    texto: 'IVA del 19% liquidado al instante y el 4x1000 que retendrá el banco al pagar.',
  },
  {
    Icon: ShieldCheckIcon,
    titulo: 'Cumplimiento DIAN y CUFE',
    texto: 'Generación de consecutivos oficiales (SETP-XXXX) y código único SHA-256.',
  },
  {
    Icon: PdfFileIcon,
    titulo: 'PDF y Envío Directo',
    texto: 'Representación gráfica lista para descargar o enviar por correo.',
  },
];

export default function Features() {
  return (
    <section id="que-hace" className={styles.section}>
      <SectionTitle titulo="¿Qué hace Alba?" subtitulo="Una plataforma pensada para ti" />

      <div className={styles.grid}>
        {FEATURES.map(({ Icon, titulo, texto }) => (
          <article key={titulo} className={styles.card}>
            <span className={styles.icon}>
              <Icon width={34} height={34} />
            </span>
            <div>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
