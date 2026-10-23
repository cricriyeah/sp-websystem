'use client';

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { ArrowsOut } from '@phosphor-icons/react';
import { columnasDeMosaico } from '@/lib/mosaico';
import { Button } from '@/components/ui/button';
import { FotoFundido } from '@/components/ui/foto-fundido';
import { VisorGaleria, type FotoVisor } from '@/components/ui/visor-galeria';
import { cn } from '@/components/ui/cn';

type Props = {
  fotos: FotoVisor[];
  textosVisor: { cerrar: string; anterior: string; siguiente: string; contador: string; pista: string };
};

// Clases completas para que Tailwind las vea: columnas de 12 en escritorio.
const COLUMNAS: Record<number, string> = {
  3: 'md:col-span-3',
  4: 'md:col-span-4',
  5: 'md:col-span-5',
  7: 'md:col-span-7',
  12: 'md:col-span-12',
};

/**
 * Las fotos de los viajes en mosaico (F10): en escritorio, filas de 12 columnas con 2, 3 o 4 fotos; en el
 * teléfono, una foto ancha y dos cuadradas, repetido. Cada foto abre el visor a pantalla completa.
 */
export function GaleriaMosaico({ fotos, textosVisor }: Props) {
  const [abierta, setAbierta] = useState<number | null>(null);
  const columnas = columnasDeMosaico(fotos.length);
  const primera = useRef<HTMLButtonElement>(null);
  const reducido = useReducedMotion();
  // «Toca para agrandar»: en pantallas táctiles (sin hover que lo insinúe), una sola vez, cuando la primera foto
  // entra a la vista. La foto se acerca apenas y regresa mientras la píldora aparece y se va (~1,6 s en total).
  const [pista, setPista] = useState(false);

  useEffect(() => {
    const el = primera.current;
    if (!el || !window.matchMedia('(hover: none)').matches) return;
    let reloj: ReturnType<typeof setTimeout> | undefined;
    const observador = new IntersectionObserver(([entrada]) => {
      if (!entrada?.isIntersecting) return;
      observador.disconnect();
      setPista(true);
      reloj = setTimeout(() => setPista(false), 1600);
    }, { threshold: 0.7 });
    observador.observe(el);
    return () => { observador.disconnect(); clearTimeout(reloj); };
  }, []);

  return (
    <>
      <div className="mt-10 grid grid-cols-2 gap-2 md:grid-cols-12 md:gap-2.5">
        {fotos.map((foto, i) => (
          <Button
            key={foto.src}
            ref={i === 0 ? primera : undefined}
            variante="libre"
            aria-haspopup="dialog"
            onClick={() => setAbierta(i)}
            className={cn(
              'group relative block cursor-zoom-in overflow-hidden bg-cafe-bruma focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              i % 3 === 0 ? 'col-span-2 aspect-[4/3]' : 'aspect-square',
              'md:aspect-auto md:h-[clamp(11rem,19vw,17rem)]',
              COLUMNAS[columnas[i]],
            )}
          >
            <FotoFundido
              src={foto.src}
              alt={foto.alt}
              fill
              loading={i < 2 ? 'eager' : 'lazy'}
              sizes="(min-width: 768px) 60vw, 100vw"
              className={cn(
                'object-cover transition-[opacity,scale,transform] duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-opacity [@media(hover:hover)]:group-hover:scale-105',
                i === 0 && pista && !reducido && 'scale-[1.03]',
              )}
            />
            {i === 0 && (
              <AnimatePresence>
                {pista && (
                  <m.span
                    initial={reducido ? { opacity: 0 } : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.45, ease: [0.2, 0, 0, 1] }}
                    className="pointer-events-none absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-tinta/80 px-4 py-2 texto-pequeno font-semibold text-white backdrop-blur-sm"
                  >
                    <ArrowsOut size={16} weight="bold" aria-hidden="true" />
                    {textosVisor.pista}
                  </m.span>
                )}
              </AnimatePresence>
            )}
          </Button>
        ))}
      </div>
      <VisorGaleria fotos={fotos} indice={abierta} onCambiar={setAbierta} textos={textosVisor} />
    </>
  );
}
