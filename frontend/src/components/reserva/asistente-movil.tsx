'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { m, useReducedMotion } from 'framer-motion';
import { DURACION, transicion } from '@/lib/movimiento';
import { useRegistroBarra, type AccionBarra } from './contexto-barra';

type Props = {
  /** Pantalla visible; al cambiar, su contenido entra y el foco va al título. */
  id: string;
  titulo: string;
  /** Primera línea de la pantalla, encima del título (p. ej. «Pago 1 de 2 · empresa · $X»). */
  antetitulo?: ReactNode;
  /** Pantallas de Pago: solo fundido, sin traslado (el formulario de Stripe no se mueve). */
  soloFundido?: boolean;
  /** «Paso 2 de 3: Tus datos»: se anuncia al cambiar de paso. */
  anuncio: string;
  /** El botón grande de abajo: «Continuar», o el de pagar en la última pantalla. */
  accion: Omit<AccionBarra, 'ejecutar'> & { alPulsar: () => void };
  children: ReactNode;
};

/**
 * Una pantalla del asistente móvil (< 640 px): título, contenido y el botón único, que se pinta
 * en la `BarraInferior`. Solo el contenido anima (`translateX(24px) → 0`, 250 ms; Pago, fundido de
 * 150 ms): la barra y la cabecera son hermanas, nunca hijas, porque un ancestro con `transform`
 * rompe `position: fixed`. Con «reducir movimiento», solo fundido.
 */
export function AsistenteMovil({ id, titulo, antetitulo, soloFundido, anuncio, accion, children }: Props) {
  const sinMovimiento = useReducedMotion();
  const { setAccion } = useRegistroBarra();
  const tituloRef = useRef<HTMLHeadingElement>(null);
  const primera = useRef(true);

  // La barra recibe una función estable que lee la acción vigente: publicar un objeto nuevo en
  // cada render volvería a pintar la barra sin fin.
  const alPulsar = useRef(accion.alPulsar);
  useEffect(() => { alPulsar.current = accion.alPulsar; });
  const { etiqueta, deshabilitado, razon, cargando, etiquetaCargando } = accion;
  useEffect(() => {
    setAccion({ etiqueta, deshabilitado, razon, cargando, etiquetaCargando, ejecutar: () => alPulsar.current() });
  }, [setAccion, etiqueta, deshabilitado, razon, cargando, etiquetaCargando]);
  useEffect(() => () => setAccion(null), [setAccion]);

  // Cambio de pantalla: arriba de la página y foco al título (el lector lo lee). En la primera
  // pintura no se mueve nada: el cliente acaba de llegar.
  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      return;
    }
    window.scrollTo({ top: 0, behavior: 'instant' });
    tituloRef.current?.focus({ preventScroll: true });
  }, [id]);

  const fundido = soloFundido || sinMovimiento;
  return (
    <>
      <p className="sr-only" aria-live="polite">{anuncio}</p>
      <m.section
        key={id}
        aria-labelledby={`pantalla-${id}`}
        initial={fundido ? { opacity: 0 } : { opacity: 0, x: 24 }}
        animate={fundido ? { opacity: 1 } : { opacity: 1, x: 0 }}
        transition={transicion(sinMovimiento, soloFundido ? DURACION.corta : DURACION.media)}
        className="flex min-w-0 flex-col gap-6"
      >
        <header className="flex flex-col gap-1">
          {antetitulo ? <div className="texto-pequeno font-semibold text-apagado">{antetitulo}</div> : null}
          <h2 id={`pantalla-${id}`} ref={tituloRef} tabIndex={-1} className="texto-paso text-foreground outline-none">
            {titulo}
          </h2>
        </header>
        {children}
      </m.section>
    </>
  );
}
