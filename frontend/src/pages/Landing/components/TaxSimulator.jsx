import { useMemo, useState } from 'react';
import { CalculatorIcon, CheckIcon } from '@/components/icons';
import { formatCOP } from '@/utils/format';
import { liquidar } from '@/utils/impuestos';
import SectionTitle from './SectionTitle';
import styles from './TaxSimulator.module.css';

const miles = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const MAX_DIGITOS = 13;

export default function TaxSimulator() {
  const [valor, setValor] = useState('100000'); // solo dígitos

  const calc = useMemo(() => liquidar(valor), [valor]);

  const handleChange = (e) => {
    const digitos = e.target.value.replace(/\D/g, '').replace(/^0+/, '').slice(0, MAX_DIGITOS);
    setValor(digitos);
  };

  return (
    <section id="simulador" className={styles.section}>
      <SectionTitle
        titulo="Simula tus impuestos"
        subtitulo="Calcula lo que pagará tu cliente antes de emitir la factura"
      />

      <div className={styles.layout}>
        <div className={styles.copy}>
          <h3>Así liquida Alba cada factura</h3>
          <p>
            Usamos las mismas reglas con las que la API emite tus facturas, así que lo que ves aquí
            es exactamente lo que quedará en el documento.
          </p>
          <ul>
            <li>
              <CheckIcon width={18} height={18} />
              <span>
                <strong>IVA del 19%</strong> sobre la base gravable.
              </span>
            </li>
            <li>
              <CheckIcon width={18} height={18} />
              <span>
                <strong>Total</strong> = subtotal + IVA, en pesos colombianos.
              </span>
            </li>
            <li>
              <CheckIcon width={18} height={18} />
              <span>
                <strong>4x1000 (0.4%)</strong> calculado sobre el total: lo retiene el banco cuando se
                paga, por eso se muestra aparte y no se suma a la factura.
              </span>
            </li>
          </ul>
        </div>

        <article className={styles.card}>
          <header className={styles.cardHeader}>
            <span className={styles.cardIcon}>
              <CalculatorIcon width={30} height={30} />
            </span>
            <h3>
              Simulador Rápido
              <br />
              de Impuestos DIAN
            </h3>
          </header>

          <label className={styles.label} htmlFor="sim-valor">
            Ingresa el valor de tu factura:
          </label>
          <div className={styles.inputWrap}>
            <span>$</span>
            <input
              id="sim-valor"
              inputMode="numeric"
              autoComplete="off"
              placeholder="0"
              value={valor ? miles.format(Number(valor)) : ''}
              onChange={handleChange}
            />
          </div>

          <dl className={styles.rows}>
            <div>
              <dt>IVA (19%)</dt>
              <dd>{formatCOP(calc.iva)}</dd>
            </div>
          </dl>

          <div className={styles.total} aria-live="polite">
            <span>Total a pagar</span>
            <strong>{formatCOP(calc.total)}</strong>
          </div>

          <p className={styles.gmf}>
            <span>4x1000 que retendrá el banco al pagar</span>
            <strong>{formatCOP(calc.gmf)}</strong>
          </p>
          <p className={styles.gmfNote}>Informativo · no se suma al total de la factura</p>
        </article>
      </div>
    </section>
  );
}
