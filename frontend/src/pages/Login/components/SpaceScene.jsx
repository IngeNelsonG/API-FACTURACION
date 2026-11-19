import styles from './SpaceScene.module.css';

/*
 * Escena decorativa del login (planetas, estrellas, cohete, estela y nubes).
 * Un solo SVG con las coordenadas del mockup (1600x900). Con
 * preserveAspectRatio="xMaxYMid slice" siempre queda anclado a la derecha,
 * así el borde de nubes coincide con el panel blanco del formulario.
 */

// Borde de nubes blancas (x, y, radio) recorriendo de arriba a abajo
const CLOUD_EDGE = [
  [1095, -10, 80], [1055, 70, 70], [1020, 150, 78], [1000, 240, 72],
  [985, 320, 66], [968, 400, 74], [955, 480, 70], [935, 560, 72],
  [880, 630, 78], [810, 700, 82], [735, 765, 85], [660, 830, 88], [600, 900, 90],
];

// Capa rosada translúcida detrás del borde (da profundidad)
const CLOUD_BACK = [
  [1010, 10, 95], [950, -20, 70], [945, 120, 60], [925, 260, 58], [905, 380, 62],
  [890, 500, 60], [850, 590, 70], [760, 650, 80], [690, 720, 78], [600, 780, 90],
  [500, 840, 100], [400, 900, 95],
];

// Capa más lejana (más oscura y transparente)
const CLOUD_FAR = [
  [900, 40, 70], [870, 200, 55], [850, 330, 50], [820, 470, 55],
  [760, 560, 70], [650, 640, 80], [540, 720, 85], [430, 800, 95], [300, 880, 100],
];

const STARS = [
  [520, 92, 6], [735, 100, 3], [612, 267, 4.5], [155, 290, 3.5], [857, 362, 3.5],
  [835, 487, 5.5], [293, 697, 5.5], [458, 672, 3], [204, 828, 3.5], [380, 160, 2.5],
];

// Polígono que rellena todo lo que queda a la derecha del borde de nubes
const fillPath =
  `M ${CLOUD_EDGE.map(([x, y]) => `${x + 25} ${y}`).join(' L ')} L 1700 1000 L 1700 -100 Z`;

export default function SpaceScene() {
  return (
    <svg
      className={styles.scene}
      viewBox="0 0 1600 900"
      preserveAspectRatio="xMaxYMid slice"
      aria-hidden
    >
      <defs>
        <radialGradient id="cloudPuff" cx="45%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="75%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#f7e6ee" />
        </radialGradient>
        <linearGradient id="trail" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="55%" stopColor="#f6dbe7" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#f6dbe7" stopOpacity="0.15" />
        </linearGradient>
        <linearGradient id="rocketBody" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="#f6f2f6" />
          <stop offset="100%" stopColor="#d9d0dc" />
        </linearGradient>
        <radialGradient id="flame" cx="50%" cy="20%" r="80%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#ffd9e6" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Planetas y halos */}
      <circle cx="-30" cy="-50" r="270" fill="#8c1944" opacity="0.55" />
      <circle cx="700" cy="470" r="300" fill="#ffffff" opacity="0.035" />
      <circle cx="840" cy="185" r="95" fill="#93204d" opacity="0.8" />
      <circle cx="55" cy="745" r="110" fill="#8e1845" />
      <circle cx="420" cy="850" r="140" fill="#a33a66" opacity="0.55" />

      {/* Estrellas */}
      <g className={styles.stars}>
        {STARS.map(([x, y, r], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={r}
            fill="#ffffff"
            opacity={0.55}
            style={{ animationDelay: `${(i % 5) * 0.6}s` }}
          />
        ))}
      </g>
      <path
        className={styles.sparkle}
        d="M885 150 Q888 169 907 172 Q888 175 885 194 Q882 175 863 172 Q882 169 885 150 Z"
        fill="#ffffff"
      />

      {/* Estela del cohete */}
      <g opacity="0.9">
        <path
          d="M668 448 C 590 520 545 610 560 700 C 575 790 650 850 720 900 L 560 900
             C 470 820 455 700 490 610 C 525 525 590 470 648 430 Z"
          fill="url(#trail)"
          opacity="0.55"
        />
        <path
          d="M672 452 C 615 520 590 600 605 680 C 620 760 680 820 760 870
             C 650 840 585 770 570 690 C 555 600 600 510 655 440 Z"
          fill="#ffffff"
          opacity="0.5"
        />
        <path
          d="M676 456 C 640 510 625 570 635 630 C 645 690 690 740 740 770
             C 670 750 620 700 610 630 C 600 560 630 495 662 446 Z"
          fill="#ffffff"
          opacity="0.75"
        />
      </g>

      {/* Nubes: capa lejana → media → borde blanco */}
      <g fill="#d68aab" opacity="0.35">
        {CLOUD_FAR.map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r} />
        ))}
      </g>
      <g fill="#f4d2e1" opacity="0.7">
        {CLOUD_BACK.map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r} />
        ))}
      </g>
      <g>
        {CLOUD_EDGE.map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r} fill="url(#cloudPuff)" />
        ))}
        <path d={fillPath} fill="#ffffff" />
      </g>

      {/* Cohete (flota suavemente) */}
      <g className={styles.rocketFloat}>
        <g transform="translate(722 372) rotate(38)">
          {/* Llama */}
          <path d="M-20 72 Q0 150 20 72 Z" fill="url(#flame)" />
          {/* Aletas laterales */}
          <path d="M-38 8 C-74 28 -86 70 -80 100 L-38 62 Z" fill="#a51d4c" />
          <path d="M38 8 C74 28 86 70 80 100 L38 62 Z" fill="#8a1540" />
          {/* Cuerpo */}
          <path
            d="M0 -112 C42 -82 50 -20 40 62 L-40 62 C-50 -20 -42 -82 0 -112 Z"
            fill="url(#rocketBody)"
          />
          {/* Punta */}
          <path
            d="M0 -112 C22 -96 33 -76 37 -56 L-37 -56 C-33 -76 -22 -96 0 -112 Z"
            fill="#b02652"
          />
          {/* Tobera */}
          <rect x="-26" y="60" width="52" height="12" rx="4" fill="#cfc6d2" />
          {/* Aleta central */}
          <path d="M-7 44 L7 44 L5 104 L-5 104 Z" fill="#7a1035" />
          {/* Ventana */}
          <circle cx="0" cy="-14" r="24" fill="#ffffff" stroke="#7a1035" strokeWidth="8" />
          <circle cx="0" cy="-14" r="15" fill="#5e0d2f" />
          <circle cx="-5" cy="-19" r="5" fill="#ffffff" opacity="0.6" />
        </g>
      </g>
    </svg>
  );
}
