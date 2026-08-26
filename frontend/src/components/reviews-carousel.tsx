'use client';

import { useEffect, useState } from 'react';
import { CaretLeft, CaretRight, Star } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

type Resena = { quote: string; author: string };

type ReviewsCarouselProps = {
  resenas: Resena[];
  prevLabel: string;
  nextLabel: string;
};

/** Cuanto dura cada reseña en pantalla antes de pasar a la siguiente. */
const INTERVALO_MS = 7000;

/**
 * Una reseña a la vez, con flechas y puntos. Avanza sola cada `INTERVALO_MS`,
 * pero se detiene con el mouse encima o el foco del teclado dentro — es texto
 * para leer, no una foto de fondo, y avanzarlo solo mientras alguien esta a
 * medio parrafo se lo tumba.
 *
 * Con `prefers-reduced-motion` no avanza sola: se queda en la primera y solo
 * cambia con las flechas o los puntos.
 */
export function ReviewsCarousel({ resenas, prevLabel, nextLabel }: ReviewsCarouselProps) {
  const [activa, setActiva] = useState(0);
  const [enPausa, setEnPausa] = useState(false);
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    if (sinMovimiento || enPausa || resenas.length < 2) return;
    const id = setInterval(() => {
      setActiva((i) => (i + 1) % resenas.length);
    }, INTERVALO_MS);
    return () => clearInterval(id);
  }, [sinMovimiento, enPausa, resenas.length]);

  const ir = (i: number) => setActiva((i + resenas.length) % resenas.length);

  const actual = resenas[activa];

  return (
    <div
      className="relative"
      onMouseEnter={() => setEnPausa(true)}
      onMouseLeave={() => setEnPausa(false)}
      onFocus={() => setEnPausa(true)}
      onBlur={() => setEnPausa(false)}
    >
      <div className="flex items-start gap-4 sm:gap-6">
        <button
          type="button"
          onClick={() => ir(activa - 1)}
          aria-label={prevLabel}
          className="mt-2 hidden h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground sm:flex"
        >
          <CaretLeft size={18} />
        </button>

        {/* Alto fijo: sin el, cada reseña de largo distinto haria brincar todo
            lo que viene debajo (los puntos, el CTA) al cambiar de una a otra. */}
        <div className="min-h-[220px] flex-1 overflow-hidden sm:min-h-[180px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={activa}
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, x: -16 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col gap-4"
            >
              <div className="flex gap-1">
                {Array.from({ length: 5 }, (_, s) => (
                  <Star key={s} size={18} weight="fill" className="text-amber" />
                ))}
              </div>
              <p className="max-w-[48ch] text-2xl leading-snug font-medium tracking-tight text-foreground">
                {actual.quote}
              </p>
              <span className="text-sm text-muted">{actual.author}</span>
            </motion.div>
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={() => ir(activa + 1)}
          aria-label={nextLabel}
          className="mt-2 hidden h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface hover:text-foreground sm:flex"
        >
          <CaretRight size={18} />
        </button>
      </div>

      <div className="mt-8 flex items-center gap-4 sm:pl-[52px]">
        <div className="flex items-center gap-2">
          {resenas.map((resena, i) => (
            <button
              key={resena.author}
              type="button"
              onClick={() => ir(i)}
              aria-label={resena.author}
              aria-current={i === activa}
              className={`h-2 rounded-full transition-all ${
                i === activa ? 'w-6 bg-action' : 'w-2 bg-border-strong'
              }`}
            />
          ))}
        </div>

        {/* Las mismas flechas de arriba, pero visibles en movil: ahi no hay
            espacio a los lados de la cita para ponerlas junto al texto. */}
        <div className="flex items-center gap-1 sm:hidden">
          <button
            type="button"
            onClick={() => ir(activa - 1)}
            aria-label={prevLabel}
            className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-foreground"
          >
            <CaretLeft size={16} />
          </button>
          <button
            type="button"
            onClick={() => ir(activa + 1)}
            aria-label={nextLabel}
            className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-foreground"
          >
            <CaretRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
