'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';

/**
 * Un texto largo que ocupa a lo más dos renglones y, si no cabe, se abre con una flecha a su lado. La
 * banda de «continuar reservación» lo usa: sus frases llegan a 150 caracteres y la hacían altísima. El
 * texto completo sigue en el árbol (solo se recorta con CSS), así que un lector de pantalla lo lee entero.
 */
export function TextoPlegable({ children, abrir, cerrar }: { children: ReactNode; abrir: string; cerrar: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [abierto, setAbierto] = useState(false);
  const [recortado, setRecortado] = useState(false);

  useEffect(() => {
    const elemento = ref.current;
    if (!elemento) return;
    const medir = () => {
      if (!abierto) setRecortado(elemento.scrollHeight > elemento.clientHeight + 1);
    };
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => observador.disconnect();
  }, [abierto, children]);

  return (
    <div className="flex min-w-0 items-center gap-3">
      <span ref={ref} className={cn('min-w-0 flex-1 texto-cuerpo', !abierto && 'line-clamp-2')}>{children}</span>
      {(recortado || abierto) && (
        <Button
          variante="libre"
          aria-expanded={abierto}
          aria-label={abierto ? cerrar : abrir}
          onClick={() => setAbierto((v) => !v)}
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-white/15 transition-colors hover:bg-white/25"
        >
          <CaretDown size={18} weight="bold" aria-hidden="true" className={cn('transition-transform duration-200', abierto && 'rotate-180')} />
        </Button>
      )}
    </div>
  );
}
