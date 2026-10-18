'use client';

import { useId, useState } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { Button } from '@/components/ui/button';

type FaqSectionProps = {
  faq: Dictionary['faq'];
};

/**
 * Acordeon en dos columnas: el titulo fijo a la izquierda, las preguntas a la
 * derecha.
 *
 * Era `<details>`/`<summary>` nativo, que da el comportamiento gratis pero abre
 * de golpe: el navegador no anima el alto de un `<details>`, asi que la
 * respuesta aparecia entera de un cuadro al otro y empujaba las preguntas de
 * abajo sin transicion. Aqui el estado es propio para poder animar ese alto
 * (`height: auto` interpolado por la libreria) y mantener el resto del bloque
 * moviendose junto con el.
 *
 * Lo que daba el marcado nativo se repone a mano: el disparador es un `<button>`
 * real —no un `<div>` con `onClick`— con `aria-expanded` y `aria-controls`, y el
 * panel se enlaza de vuelta con `aria-labelledby`. Con eso un lector de pantalla
 * anuncia lo mismo que anunciaba antes.
 *
 * Solo se abre una a la vez: son catorce preguntas y con varias abiertas la
 * columna se vuelve un muro de texto donde ya no se ve que mas hay.
 */
export function FaqSection({ faq }: FaqSectionProps) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const sinMovimiento = useReducedMotion();
  const idBase = useId();

  return (
    <section id="preguntas" className="scroll-mt-24 bg-surface py-24 lg:py-32">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 sm:px-8 lg:grid-cols-[280px_1fr] lg:gap-20 lg:px-12">
        {/* La barra y el titular van envueltos: son la primera **columna** del
            grid, no dos celdas. Sueltos, la barra ocupaba la celda del titular
            y empujaba las preguntas a una fila nueva. */}
        <div>
          <h2 className="texto-seccion text-foreground">
            {faq.headline}
          </h2>
        </div>

        <div className="flex flex-col">
          {faq.items.map((item, i) => {
            const abierto = abierta === item.q;
            const idPregunta = `${idBase}-p${i}`;
            const idRespuesta = `${idBase}-r${i}`;

            return (
              <div key={item.q} className="group border-b border-border-strong">
                <h3>
                  <Button
                    variante="fila"
                    id={idPregunta}
                    aria-expanded={abierto}
                    aria-controls={idRespuesta}
                    onClick={() => setAbierta(abierto ? null : item.q)}
                  >
                    <span className="transition-colors group-hover:text-accent">{item.q}</span>
                    {/* Cruz que se vuelve guion: la barra vertical se aplasta a
                        cero. Es la misma pieza en los dos estados, asi que el
                        cambio se lee como un giro y no como dos iconos
                        distintos intercambiandose. */}
                    <span className="relative size-5 shrink-0 text-accent transition-transform duration-200 group-hover:scale-110">
                      <span className="absolute inset-y-1/2 left-0 h-0.5 w-full -translate-y-1/2 bg-current" />
                      <span
                        className={`absolute inset-x-1/2 top-0 h-full w-0.5 -translate-x-1/2 bg-current transition-transform duration-200 ${
                          abierto ? 'scale-y-0' : 'scale-y-100'
                        }`}
                      />
                    </span>
                  </Button>
                </h3>

                <AnimatePresence initial={false}>
                  {abierto && (
                    <m.div
                      key="respuesta"
                      id={idRespuesta}
                      role="region"
                      aria-labelledby={idPregunta}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={
                        sinMovimiento
                          ? { duration: 0 }
                          : {
                              height: { duration: 0.32, ease: [0.16, 1, 0.3, 1] },
                              // La opacidad va mas corta que el alto para que el
                              // texto no se lea a medio desplegar.
                              opacity: { duration: 0.2 },
                            }
                      }
                      // El alto se anima sobre el contenedor de afuera, asi que
                      // el padding tiene que vivir adentro: en el de afuera se
                      // sumaria al alto 0 y dejaria una franja abierta.
                      className="overflow-hidden"
                    >
                      <p className="max-w-[65ch] pb-5 pr-10 text-base leading-relaxed text-muted">
                        {item.a}
                      </p>
                    </m.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
