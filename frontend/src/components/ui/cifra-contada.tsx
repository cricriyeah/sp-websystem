'use client';

import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { partirCifra, valorContado } from '@/lib/cifra';

const DURACION_MS = 900;

/**
 * Una cifra («30 %», «48 h») que cuenta desde cero una sola vez al entrar en pantalla. El HTML inicial ya
 * trae el valor final: sin JavaScript, o con «reducir movimiento», se ve quieta y completa. Pensada para
 * ir en un `<strong>` con `tabular-nums`, que evita que el ancho baile mientras cuenta.
 */
export function CifraContada({ cifra, className }: { cifra: string; className?: string }) {
  const partes = partirCifra(cifra);
  const reducido = useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const [valor, setValor] = useState(partes?.valor ?? 0);

  useEffect(() => {
    const el = ref.current;
    const meta = partirCifra(cifra)?.valor;
    if (!el || meta === undefined || reducido) return;
    let cuadro = 0;
    setValor(0);
    const observador = new IntersectionObserver(([entrada]) => {
      if (!entrada.isIntersecting) return;
      observador.disconnect();
      const inicio = performance.now();
      const paso = (ahora: number) => {
        const progreso = (ahora - inicio) / DURACION_MS;
        setValor(valorContado(meta, progreso));
        if (progreso < 1) cuadro = requestAnimationFrame(paso);
      };
      cuadro = requestAnimationFrame(paso);
    }, { threshold: 0.6 });
    observador.observe(el);
    return () => {
      observador.disconnect();
      cancelAnimationFrame(cuadro);
    };
  }, [cifra, reducido]);

  return (
    <strong ref={ref} className={className}>
      {partes ? `${valor}${partes.sufijo}` : cifra}
    </strong>
  );
}
