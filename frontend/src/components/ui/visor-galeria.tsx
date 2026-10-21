'use client';

import { useEffect, useRef, type KeyboardEvent } from 'react';
import Image from 'next/image';
import { ArrowLeft, ArrowRight, X } from '@phosphor-icons/react/ssr';
import { Button } from './button';

export type FotoVisor = { src: string; alt: string; ancho: number; alto: number; leyenda?: string };

type Props = {
  fotos: FotoVisor[];
  /** Índice de la foto abierta; `null` = cerrado. El padre manda. */
  indice: number | null;
  onCambiar: (indice: number | null) => void;
  textos: { cerrar: string; anterior: string; siguiente: string; contador: string };
};

/**
 * Visor de fotos a pantalla completa sobre `<dialog>` + `showModal()`: el navegador pone la trampa de foco,
 * vuelve inerte el resto de la página, cierra con Esc y devuelve el foco a la foto que se tocó. Flechas
 * en pantalla y del teclado. La foto grande solo se carga al abrir. Controlado: el padre manda `indice`.
 */
export function VisorGaleria({ fotos, indice, onCambiar, textos }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const abierto = indice !== null;

  useEffect(() => {
    const el = dialogo.current;
    if (!el) return;
    if (abierto && !el.open) el.showModal();
    if (!abierto && el.open) el.close();
  }, [abierto]);

  const foto = indice === null ? null : fotos[indice];
  const ir = (paso: -1 | 1) => {
    if (indice !== null) onCambiar((indice + paso + fotos.length) % fotos.length);
  };
  const alTeclear = (evento: KeyboardEvent<HTMLDialogElement>) => {
    if (evento.key === 'ArrowLeft') ir(-1);
    if (evento.key === 'ArrowRight') ir(1);
  };

  return (
    <dialog
      ref={dialogo}
      aria-label={foto?.alt}
      onKeyDown={alTeclear}
      onClose={() => onCambiar(null)}
      className="fixed inset-0 m-0 h-svh max-h-none w-screen max-w-none bg-tinta p-0 text-hero-ink backdrop:bg-tinta open:flex open:flex-col"
    >
      {foto && indice !== null && (
        <>
          <div className="flex items-center justify-between gap-4 px-4 pb-2 pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-6 lg:px-12">
            <p className="texto-cuerpo font-semibold">
              {textos.contador.replace('{n}', String(indice + 1)).replace('{total}', String(fotos.length))}
              {foto.leyenda && <span className="font-normal"> · {foto.leyenda}</span>}
            </p>
            <Button variante="campana-claro" tamano="icono" aria-label={textos.cerrar} onClick={() => onCambiar(null)}>
              <X size={24} weight="bold" aria-hidden="true" />
            </Button>
          </div>
          <div key={foto.src} className="rev-visor relative min-h-0 flex-1">
            <Image src={foto.src} alt={foto.alt} fill sizes="100vw" className="object-contain" />
          </div>
          <div className="flex justify-center gap-2 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4">
            <Button variante="campana-claro" tamano="icono" aria-label={textos.anterior} onClick={() => ir(-1)}>
              <ArrowLeft size={20} weight="bold" aria-hidden="true" />
            </Button>
            <Button variante="campana-claro" tamano="icono" aria-label={textos.siguiente} onClick={() => ir(1)}>
              <ArrowRight size={20} weight="bold" aria-hidden="true" />
            </Button>
          </div>
        </>
      )}
    </dialog>
  );
}
