// Íconos SVG en línea (sin librerías externas). Heredan el color con currentColor.
const base = {
  width: 24,
  height: 24,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
};

export const UserIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
  </svg>
);

export const LockIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="4.5" y="10.5" width="15" height="10.5" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </svg>
);

export const EyeIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const EyeOffIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-2.6 3.5" />
    <path d="M6.6 6.6C3.7 8.4 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 5.4-1.6" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    <path d="M3 3l18 18" />
  </svg>
);

export const ArrowRightIcon = (props) => (
  <svg {...base} strokeWidth={2.2} {...props}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const ShieldCheckIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6L12 3Z" />
    <path d="m8.8 12.2 2.3 2.3 4.3-4.6" />
  </svg>
);

export const LogoutIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
    <path d="M10 17l-5-5 5-5M5 12h11" />
  </svg>
);

/* ---------- Íconos del dashboard ---------- */
export const HomeIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
  </svg>
);

export const FileTextIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
    <path d="M14 3v5h5M9 13h6M9 17h6M9 9h2" />
  </svg>
);

export const UsersIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.3c2.1.7 3.5 2.8 3.5 5.7" />
  </svg>
);

export const BarChartIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M5 20v-6M12 20V9M19 20V4" strokeWidth={3} />
  </svg>
);

export const SettingsIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
  </svg>
);

export const SearchIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const BellIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
    <path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" />
  </svg>
);

export const CheckIcon = (props) => (
  <svg {...base} strokeWidth={2.6} {...props}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
);

export const ClockIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const XIcon = (props) => (
  <svg {...base} strokeWidth={2.4} {...props}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const DownloadIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 4v11M7 10.5l5 5 5-5M5 20h14" />
  </svg>
);

export const MoreIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="5" r="1.4" fill="currentColor" />
    <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    <circle cx="12" cy="19" r="1.4" fill="currentColor" />
  </svg>
);

export const PlusIcon = (props) => (
  <svg {...base} strokeWidth={2.4} {...props}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const ChevronRightIcon = (props) => (
  <svg {...base} strokeWidth={2.2} {...props}>
    <path d="m9 6 6 6-6 6" />
  </svg>
);

export const ChevronDownIcon = (props) => (
  <svg {...base} strokeWidth={2.2} {...props}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const MenuIcon = (props) => (
  <svg {...base} strokeWidth={2.2} {...props}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

export const TrendUpIcon = (props) => (
  <svg {...base} strokeWidth={2.4} {...props}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </svg>
);

export const TrendDownIcon = (props) => (
  <svg {...base} strokeWidth={2.4} {...props}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </svg>
);

/* ---------- Íconos de la landing ---------- */
export const CalculatorIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="4.5" y="2.5" width="15" height="19" rx="2.5" />
    <rect x="7.5" y="5.5" width="9" height="4" rx="1" />
    <path d="M8 13h.01M12 13h.01M16 13h.01M8 16.5h.01M12 16.5h.01M16 16.5h.01M8 19h.01M12 19h.01M16 19h.01" strokeWidth={2.6} />
  </svg>
);

export const PdfFileIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M14 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8L14 2.5Z" />
    <path d="M14 2.5V8h5.5" />
    <text x="12" y="17.5" textAnchor="middle" fontSize="6" fontWeight="700" fill="currentColor" stroke="none" fontFamily="Poppins, sans-serif">
      PDF
    </text>
  </svg>
);

export const SendIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M21.5 2.5 10 14" />
    <path d="M21.5 2.5 14.5 21.5 10 14 2.5 9.5l19-7Z" />
  </svg>
);

/* ---------- Íconos de Facturas ---------- */
export const EyeOpenIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const ShareIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="18" cy="5" r="2.6" />
    <circle cx="6" cy="12" r="2.6" />
    <circle cx="18" cy="19" r="2.6" />
    <path d="m8.3 10.8 7.4-4.3M8.3 13.2l7.4 4.3" />
  </svg>
);

export const CalendarIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  </svg>
);

export const RefreshIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M20 11a8 8 0 1 0-2.3 5.7" />
    <path d="M20 4v7h-7" />
  </svg>
);

export const ChevronLeftIcon = (props) => (
  <svg {...base} strokeWidth={2.2} {...props}>
    <path d="m15 6-6 6 6 6" />
  </svg>
);
