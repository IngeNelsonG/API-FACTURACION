import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <main style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', textAlign: 'center' }}>
      <div>
        <h1 style={{ fontSize: '4rem', margin: 0, color: 'var(--color-primary-700)' }}>404</h1>
        <p>La página que buscas no existe.</p>
        <Link to="/" style={{ color: 'var(--color-primary-600)' }}>
          Volver al inicio
        </Link>
      </div>
    </main>
  );
}
