'use client';

import { useId, useState } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { Minus, Plus } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';

type FaqSectionProps = {
  id: string;
  titulo: string;
  /** Las preguntas salen del cuerpo de la sede. */
  preguntas: { q: string; a: string }[];
  fondo: Fondo;
  borde: boolean;
  /** Cierre del bloque: «Si no encuentras tu duda…» al WhatsApp único. Sin número no se pinta. */
  whatsapp: { texto: string; href: string } | null;
};

const MAX_PREGUNTAS = 8;

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
 * Solo se abre una a la vez: son hasta ocho preguntas y con varias abiertas la
 * columna se vuelve un muro de texto donde ya no se ve que mas hay.
 */
export function FaqSection({ id, titulo, preguntas, fondo, borde, whatsapp }: FaqSectionProps) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const sinMovimiento = useReducedMotion();
  const idBase = useId();

  return (
    <section id={id} className={`scroll-mt-24 ${CLASE_FONDO[fondo]} ${borde ? 'border-t border-borde ' : ''}py-24 lg:py-32`}>
      <div className="mx-auto grid max-w-[1120px] gap-10 px-4 sm:px-6 lg:grid-cols-[280px_1fr] lg:gap-20 lg:px-8">
        {/* La barra y el titular van envueltos: son la primera **columna** del
            grid, no dos celdas. Sueltos, la barra ocupaba la celda del titular
            y empujaba las preguntas a una fila nueva. */}
        <div>
          <h2 className="texto-seccion text-foreground">
            {titulo}
          </h2>
        </div>

        <div className="flex flex-col">
          {preguntas.slice(0, MAX_PREGUNTAS).map((item, i) => {
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
                    {abierto
                      ? <Minus size={20} aria-hidden="true" className="shrink-0 text-cafe" />
                      : <Plus size={20} aria-hidden="true" className="shrink-0 text-cafe" />}
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
                              height: { duration: 0.25, ease: [0.16, 1, 0.3, 1] },
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
          {whatsapp && (
            <a href={whatsapp.href} target="_blank" rel="noopener noreferrer" className="mt-6 inline-flex min-h-11 items-center self-start texto-cuerpo font-semibold text-cafe">
              {whatsapp.texto}
            </a>
          )}
        </div>
      </div>
    </section>
  );
}
