'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import Image from 'next/image';
import type { SedeTemporadas } from '@/content/sedes-tipos';
import { temporadaDeMes } from '@/lib/temporada-actual';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';

const suscribirseAlMes = () => () => {};
const sinCambios = () => () => {};
const quiereMenosMovimiento = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

type Props = {
  temporadas: SedeTemporadas;
  textos: { ahora: string };
};

/**
 * El calendario de especies, rediseñado con Apple Design (dueño, 2026-11-07: «se ve puro texto cuando eliges y
 * tienes que bajar para ver la imagen»). Lo que se toca y lo que cambia van pegados:
 *
 * - Arriba, un control segmentado con las temporadas; la pastilla se desliza a la elegida y la de hoy dice «ahora».
 * - Debajo, una escena por temporada en un carrusel con scroll-snap: foto y texto en el mismo cuadro, así que al
 *   elegir no hay que bajar. En el teléfono el texto va sobre la foto (4:5, con degradado); desde md, foto a la
 *   izquierda y texto a su lado, porque las fotos son verticales y a todo lo ancho se recortarían.
 * - El carrusel es scroll nativo: el dedo (o el trackpad) lo arrastra 1:1 y suelta con el impulso del sistema. El
 *   segmentado lo sigue al terminar en una escena; tocar un segmento lo lleva ahí (sin animación con «reducir
 *   movimiento»).
 *
 * Arranca en la temporada del mes de hoy o, sin ella, en la fuerte.
 */
export function TemporadasSelector({ temporadas, textos }: Props) {
  const { filas } = temporadas;
  const fuerte = Math.max(0, filas.findIndex((fila) => fila.fuerte));
  // El mes de hoy es del navegador: el servidor no lo sabe (-1) y el cliente lo lee al hidratar.
  const mes = useSyncExternalStore(suscribirseAlMes, () => new Date().getMonth(), () => -1);
  const menosMovimiento = useSyncExternalStore(sinCambios, quiereMenosMovimiento, () => false);
  const hoy = temporadaDeMes(filas, mes);
  const inicial = hoy >= 0 ? hoy : fuerte;
  const [tocada, setTocada] = useState<number | null>(null);
  const activa = tocada ?? inicial;

  const carril = useRef<HTMLDivElement>(null);
  // Mientras el carrusel va a una escena elegida en el segmentado, las escenas por las que pasa no cambian la pastilla.
  const destino = useRef<number | null>(null);

  // Antes de que el cliente toque nada, el carril se coloca (sin animar) en la temporada de hoy.
  useEffect(() => {
    const el = carril.current;
    if (!el || tocada !== null) return;
    el.scrollLeft = inicial * el.clientWidth;
  }, [inicial, tocada]);

  const elegir = (i: number) => {
    const el = carril.current;
    setTocada(i);
    if (!el) return;
    destino.current = i;
    el.scrollTo({ left: i * el.clientWidth, behavior: menosMovimiento ? 'auto' : 'smooth' });
  };

  // Si el cliente toma el carrusel con el dedo o la rueda a medio camino, manda él: se olvida el destino.
  const soltarDestino = () => {
    destino.current = null;
  };

  // Al detenerse el scroll (llegue o no al destino) la pastilla queda en la escena donde paró.
  useEffect(() => {
    const el = carril.current;
    if (!el) return;
    const alParar = () => {
      destino.current = null;
      if (el.clientWidth === 0) return;
      setTocada(Math.round(el.scrollLeft / el.clientWidth));
    };
    el.addEventListener('scrollend', alParar);
    return () => el.removeEventListener('scrollend', alParar);
  }, []);

  const alDesplazar = () => {
    const el = carril.current;
    if (!el || el.clientWidth === 0) return;
    const i = Math.round(el.scrollLeft / el.clientWidth);
    if (destino.current !== null) {
      if (i !== destino.current) return;
      destino.current = null;
    }
    if (i !== activa) setTocada(i);
  };

  const corto = (meses: string[]) => (meses.length > 1 ? `${meses[0]}–${meses.at(-1)}` : meses[0]);

  return (
    <div className="mt-10 flex flex-col gap-3 sm:gap-4">
      {/* Bloques de temporada (dueño, 2026-11-07: la cápsula de iPhone no seguía el sitio): rectos, separados entre
          sí y de la escena, con el periodo centrado en la fuente de los títulos. La elegida en tinta, como el panel de
          la escena; el bloque tinta se desliza a la elegida (curva sin rebote) saltando el hueco entre bloques. */}
      <div role="group" aria-label={temporadas.etiquetaCalendario} className="relative grid gap-2" style={{ gridTemplateColumns: `repeat(${filas.length}, minmax(0, 1fr))` }}>
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 bg-tinta transition-transform duration-[450ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
          style={{
            width: `calc((100% - ${filas.length - 1} * 0.5rem) / ${filas.length})`,
            transform: `translateX(calc(${activa} * (100% + 0.5rem)))`,
          }}
        />
        {filas.map((f, i) => (
          <Button
            key={f.periodo}
            variante="libre"
            aria-pressed={i === activa}
            aria-label={i === hoy ? `${f.periodo}, ${textos.ahora}` : f.periodo}
            onClick={() => elegir(i)}
            className={cn(
              'relative z-[1] flex min-h-20 flex-col items-center justify-center gap-1.5 px-2 py-4 text-center transition-colors duration-200 focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ring sm:px-4 md:min-h-24',
              i === activa ? 'text-white' : 'bg-cafe-bruma text-foreground hover:bg-borde/60',
            )}
          >
            <span className="texto-mono-mayus text-xl font-bold leading-[1.1] text-balance md:hidden">{corto(f.meses)}</span>
            <span className="texto-mono-mayus hidden font-bold leading-[1.1] text-balance md:inline md:text-2xl lg:text-3xl">{f.periodo}</span>
            <span className={cn('texto-etiqueta', i === activa ? 'text-coral-claro' : 'text-coral-texto')}>
              {i === hoy ? textos.ahora : ''}
              {f.fuerte ? <span className={cn('hidden md:inline', i === activa ? 'text-white/70' : 'text-tinta-suave')}>{i === hoy ? ' · ' : ''}{temporadas.etiquetaFuerte}</span> : null}
            </span>
          </Button>
        ))}
      </div>

      {/* Una escena por temporada; el scroll horizontal es el gesto. */}
      <div
        ref={carril}
        onScroll={alDesplazar}
        onPointerDown={soltarDestino}
        onWheel={soltarDestino}
        onTouchStart={soltarDestino}
        aria-roledescription="carrusel"
        className="flex snap-x snap-mandatory overflow-x-auto overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {filas.map((f, i) => (
          <article
            key={f.periodo}
            aria-hidden={i !== activa}
            aria-roledescription="temporada"
            className="relative grid w-full shrink-0 snap-center snap-always overflow-hidden bg-tinta text-white md:h-[min(72vh,640px)] md:grid-cols-[3fr_2fr]"
          >
            <div className="relative aspect-[4/5] md:aspect-auto md:h-full">
              <Image src={f.foto} alt={f.estrella} fill sizes="(min-width: 768px) 58vw, 100vw" className="object-cover object-[50%_35%]" />
              {/* Teléfono: degradado para que el texto se lea sobre la foto. */}
              <div aria-hidden className="absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-black/85 via-black/45 to-transparent md:hidden" />
            </div>
            <div
              className={cn(
                'absolute inset-x-0 bottom-0 flex flex-col p-6 transition-[opacity,translate] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:translate-y-0 motion-reduce:duration-200 sm:p-8 md:static md:justify-end md:p-10 lg:p-12',
                i === activa ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0',
              )}
            >
              <p className="texto-etiqueta text-white/75">
                {f.periodo}
                {f.fuerte ? ` · ${temporadas.etiquetaFuerte}` : ''}
              </p>
              <p className="mt-3 texto-grande">{f.estrella}</p>
              <p className="mt-4 max-w-[46ch] texto-cuerpo text-white/90">{f.descripcion}</p>
              {f.otras && (
                <p className="mt-4 max-w-[46ch] texto-cuerpo text-white/90">
                  <span className="font-semibold text-white">{temporadas.etiquetaOtras}:</span> {f.otras}
                </p>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
