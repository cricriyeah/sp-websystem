'use client';

import { useEffect, useId, useRef, useState, type MouseEvent, type ReactNode, type TransitionEvent } from 'react';
import { X } from '@phosphor-icons/react/ssr';
import { cn } from './cn';
import { hojaClases } from './variantes';

type SheetProps = {
  abierto: boolean;
  /** Se llama al pedir el cierre (Esc, tocar fuera o «Cerrar»). El padre pone `abierto` en false. */
  onCerrar: () => void;
  titulo: string;
  /** Texto accesible del botón de cerrar (viene del diccionario). */
  etiquetaCerrar: string;
  /** El contenido no es una tarjeta dentro de la hoja: se le quitan borde, radio y sombra. */
  sinBorde?: boolean;
  className?: string;
  children: ReactNode;
};

/**
 * Hoja modal que sube desde abajo (móvil). Sobre `<dialog>` + `showModal()`: el
 * navegador pone la trampa de foco, vuelve inerte el resto de la página, cierra con
 * Esc y devuelve el foco al elemento que la abrió. Aquí se suma el cierre al tocar
 * fuera, el bloqueo de scroll (globals.css, `html:has(dialog:modal)`) y la
 * animación (`.hoja-dialogo`, globals.css).
 *
 * Controlada: el padre manda `abierto`. El contenido solo está en el árbol mientras
 * la hoja está abierta o saliendo, para no duplicar en el DOM lo que ya se pinta en
 * la página (p. ej. el resumen del pedido en escritorio).
 */
export function Sheet({ abierto, onCerrar, titulo, etiquetaCerrar, sinBorde = false, className, children }: SheetProps) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const idTitulo = useId();
  const clases = hojaClases({ sinBorde });

  // Último valor de `abierto` para el evento `close`: un cierre pedido por el padre
  // ya viene con `abierto` en false y no hay que avisarle de lo que él mismo hizo.
  const abiertoActual = useRef(abierto);
  const [montado, setMontado] = useState(abierto);
  if (abierto && !montado) setMontado(true);

  useEffect(() => {
    abiertoActual.current = abierto;
    const el = dialogo.current;
    if (!el) return;
    if (abierto && !el.open) el.showModal();
    if (!abierto && el.open) el.close();
  }, [abierto, montado]);

  // La salida corre por CSS; al terminar (o a los 600 ms si el navegador no animó)
  // se saca el contenido del árbol.
  useEffect(() => {
    if (abierto || !montado) return;
    const espera = window.setTimeout(() => setMontado(false), 600);
    return () => window.clearTimeout(espera);
  }, [abierto, montado]);

  const alTerminarTransicion = (evento: TransitionEvent<HTMLDialogElement>) => {
    if (evento.target === evento.currentTarget && !abiertoActual.current) setMontado(false);
  };

  // Tocar el fondo atenuado llega como un clic sobre el propio <dialog>; se distingue
  // de un clic en su relleno por las coordenadas, que caen fuera de su caja.
  const alHacerClic = (evento: MouseEvent<HTMLDialogElement>) => {
    if (evento.target !== evento.currentTarget) return;
    const caja = evento.currentTarget.getBoundingClientRect();
    const fuera =
      evento.clientX < caja.left || evento.clientX > caja.right || evento.clientY < caja.top || evento.clientY > caja.bottom;
    if (fuera) onCerrar();
  };

  return (
    <dialog
      ref={dialogo}
      aria-modal="true"
      aria-labelledby={idTitulo}
      onClick={alHacerClic}
      onClose={() => {
        if (abiertoActual.current) onCerrar();
      }}
      onTransitionEnd={alTerminarTransicion}
      className={cn(clases.dialogo, className)}
    >
      {montado && (
        <>
          <div aria-hidden="true" className={clases.asa} />
          <div className={clases.cabecera}>
            <h2 id={idTitulo} className={cn('texto-subtitulo', clases.titulo)}>
              {titulo}
            </h2>
            <button type="button" onClick={onCerrar} aria-label={etiquetaCerrar} className={clases.cerrar}>
              <X size={24} weight="bold" aria-hidden="true" />
            </button>
          </div>
          <div className={clases.cuerpo}>{children}</div>
        </>
      )}
    </dialog>
  );
}
