'use client';

import { useId, useState } from 'react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { Plus, WhatsappLogo } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { botonClases } from '@/components/ui/variantes';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

type FaqSectionProps = {
  id: string;
  titulo: string;
  /** Las preguntas salen del cuerpo de la sede. */
  preguntas: { q: string; a: string }[];
  fondo: Fondo;
  /** Cierre del bloque: «Si no encuentras tu duda…» al WhatsApp único. Sin número no se pinta. */
  whatsapp: { texto: string; boton: string; href: string } | null;
};

const MAX_PREGUNTAS = 8;

/**
 * Preguntas frecuentes (F10): el título a la izquierda y, a la derecha, un bloque por pregunta que se abre
 * con su altura (250 ms). El estado es propio, no un `<details>`, porque el navegador no anima el alto de un
 * `<details>`. El disparador es un `<button>` real con `aria-expanded` y `aria-controls`, y el panel se enlaza
 * de vuelta con `aria-labelledby`. Solo se abre una a la vez. El «+» gira a «×» al abrir.
 */
export function FaqSection({ id, titulo, preguntas, fondo, whatsapp }: FaqSectionProps) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const sinMovimiento = useReducedMotion();
  const idBase = useId();
  // El bloque se distingue del fondo con un paso de tono: gris sobre blanco, blanco sobre gris.
  const bloque = fondo === 'blanco' ? 'bg-cafe-bruma' : 'bg-superficie';

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto grid max-w-[1440px] gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] lg:gap-12 lg:px-12">
        <h2 id={`${id}-titulo`} className="rev texto-seccion">{titulo}</h2>

        <div className="flex flex-col gap-2">
          {preguntas.slice(0, MAX_PREGUNTAS).map((item, i) => {
            const abierto = abierta === item.q;
            const idPregunta = `${idBase}-p${i}`;
            const idRespuesta = `${idBase}-r${i}`;

            return (
              <div key={item.q} className={cn('group transition-colors duration-200', bloque)}>
                <h3>
                  <Button
                    variante="fila"
                    id={idPregunta}
                    aria-expanded={abierto}
                    aria-controls={idRespuesta}
                    onClick={() => setAbierta(abierto ? null : item.q)}
                    className="min-h-[4.5rem] px-6 py-5 text-xl font-semibold"
                  >
                    <span className="transition-colors group-hover:text-cafe">{item.q}</span>
                    <Plus
                      size={28}
                      aria-hidden="true"
                      className={cn('shrink-0 transition-transform duration-300 ease-[var(--curva-estandar)] motion-reduce:transition-none', abierto && 'rotate-45')}
                    />
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
                              // La opacidad va más corta que el alto para que el texto no se lea a medio desplegar.
                              opacity: { duration: 0.2 },
                            }
                      }
                      // El alto se anima sobre el contenedor de afuera: el padding vive adentro.
                      className="overflow-hidden"
                    >
                      <p className="max-w-[56ch] px-6 pb-6 texto-cuerpo">{item.a}</p>
                    </m.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
          {whatsapp && (
            <div className="mt-6 flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="texto-subtitulo">{whatsapp.texto}</p>
              <a href={whatsapp.href} target="_blank" rel="noopener noreferrer" className={botonClases({ variante: 'campana' })}>
                <WhatsappLogo size={20} weight="fill" aria-hidden="true" />
                {whatsapp.boton}
              </a>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
