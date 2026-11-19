import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import LandingHeader from './components/LandingHeader';
import Hero from './components/Hero';
import Features from './components/Features';
import TaxSimulator from './components/TaxSimulator';
import CtaBanner from './components/CtaBanner';
import LandingFooter from './components/LandingFooter';
import RegisterModal from './components/RegisterModal';

/** Página pública de inicio (index). El simulador va en el cuerpo, no en el hero. */
export default function LandingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  // Se abre directo si llegan desde "Crear cuenta" del login
  const [registroAbierto, setRegistroAbierto] = useState(Boolean(location.state?.registro));

  const abrirRegistro = () => setRegistroAbierto(true);

  const handleRegistrado = (usuario) => {
    setRegistroAbierto(false);
    navigate('/login', { state: { registrado: usuario } });
  };

  return (
    <>
      <LandingHeader onRegistro={abrirRegistro} />
      <main>
        <Hero />
        <Features />
        <TaxSimulator />
        <CtaBanner onRegistro={abrirRegistro} />
      </main>
      <LandingFooter />
      <RegisterModal
        open={registroAbierto}
        onClose={() => setRegistroAbierto(false)}
        onRegistrado={handleRegistrado}
      />
    </>
  );
}
