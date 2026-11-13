import type { ReactNode } from 'react';
import Image from 'next/image';
import { cn } from './cn';
import { SelloTitulo, type ModoSello } from './sello-titulo';

/**
 * Bandas de sección (F10): blanco, gris y la banda negra de las cifras. Las clases van completas
 * para que Tailwind las vea. `cafe-claro` (amarillo saturado) nunca es fondo de sección.
 */
export type Fondo = 'blanco' | 'cafe-bruma' | 'tinta';

export const CLASE_FONDO: Record<Fondo, string> = {
  blanco: 'bg-superficie',
  'cafe-bruma': 'bg-cafe-bruma',
  tinta: 'bg-tinta text-hero-ink',
};

const ANCHOS_TITULO = {
  '14ch': 'max-w-[14ch]',
  '16ch': 'max-w-[16ch]',
  '24ch': 'max-w-[24ch]',
} as const;

export type SectionShellProps = {
  /** Ancla de la sección (`#id`); el `<h2>` toma `${id}-titulo` para `aria-labelledby`. */
  id: string;
  fondo: Fondo;
  /** Contenido del `<h2>` de la sección. */
  titulo: ReactNode;
  /** Ancho máximo del título, en caracteres. Por defecto, 24. */
  anchoTitulo?: keyof typeof ANCHOS_TITULO;
  /** Texto que acompaña al título a su derecha en escritorio (debajo en móvil). */
  lado?: ReactNode;
  /**
   * El isotipo de la empresa arriba a la derecha, en la esquina (`SelloTitulo`). Con `sinFondo`
   * (isotipo transparente) va sin círculo en fondo claro y dentro de un círculo blanco en la banda tinta; sin él, el
   * logo con su propio círculo.
   */
  sello?: { isotipo: string; sinFondo?: string; alt: string; largo?: { src: string; ancho: number; alto: number; blanco?: string; sello?: string } };
  /**
   * Ilustración de fondo detrás del contenido (ruta bajo /public, un dibujo de un solo color): grande, en tinta muy
   * baja y cortada por el borde derecho. Decorativa: no la anuncian los lectores de pantalla.
   */
  ilustracion?: string;
  children: ReactNode;
};

function modoDeSello(fondo: Fondo, sinFondo?: string): ModoSello {
  if (!sinFondo) return 'aro-propio';
  return fondo === 'tinta' ? 'aro-fuera' : 'sin-aro';
}

/**
 * Ritmo único de las secciones de una página: banda de color (sin rayas), aire vertical, contenedor
 * de 1440 px con el margen de la página, ancla que no queda bajo la cabecera fija (`--nav-alto`) y
 * título `<h2>` enlazado con `aria-labelledby` para que los lectores de pantalla anuncien la sección
 * al llegar por el ancla. El título sube al entrar (`rev`).
 *
 * Server Component.
 */
export function SectionShell({ id, fondo, titulo, anchoTitulo = '24ch', lado, sello, ilustracion, children }: SectionShellProps) {
  const idTitulo = `${id}-titulo`;
  const h2 = <h2 id={idTitulo} className={`rev ${ANCHOS_TITULO[anchoTitulo]} texto-seccion`}>{titulo}</h2>;
  const modo = sello && modoDeSello(fondo, sello.sinFondo);
  const src = sello && (modo === 'aro-propio' ? sello.isotipo : sello.sinFondo!);
  // El sello en la esquina de arriba a la derecha (`SelloTitulo`): firma la sección sin quitarle el protagonismo.
  const bloqueTitulo = sello?.largo ? (
    // El logo largo (Sal y Sol, Piratas): del tamaño del sello y con el título bajado a su base, como en «Las pangas».
    // En la banda tinta va su versión en blanco si la tiene (el de color no se lee sobre negro).
    <div className="flex items-end justify-between gap-6">
      {h2}
      <Image src={fondo === 'tinta' && sello.largo.blanco ? sello.largo.blanco : sello.largo.src} alt={sello.alt} width={sello.largo.ancho} height={sello.largo.alto} className={cn('rev block w-auto shrink-0', sello.largo.sello ?? 'h-12 sm:h-20 lg:h-24 xl:h-28')} />
    </div>
  ) : sello && modo && src ? (
      <div className="flex items-start justify-between gap-6">
        {h2}
        <SelloTitulo src={src} alt={sello.alt} modo={modo} />
      </div>
    ) : (
      h2
    );

  return (
    <section
      id={id}
      aria-labelledby={idTitulo}
      className={`scroll-mt-[calc(var(--nav-alto)+16px)] ${CLASE_FONDO[fondo]} py-16 sm:py-20 lg:py-28${ilustracion ? ' relative isolate overflow-clip' : ''}`}
    >
      {ilustracion && (
        // En el teléfono, más grande (1,5 veces lo que era, pedido del dueño): centrada en la altura de la sección y corrida
        // a la derecha, asoman el sol y la cabeza del pez detrás de las cifras. En tableta y escritorio, más chica, a media
        // altura de la banda y cortada por el borde derecho.
        <span
          aria-hidden
          className="pointer-events-none absolute top-1/2 -right-[68%] -z-10 aspect-[1776/1481] w-[180%] -translate-y-1/2 bg-contain bg-no-repeat opacity-[0.07] sm:top-28 sm:-right-[22%] sm:w-[80%] sm:translate-y-0 lg:top-1/2 lg:-right-[6%] lg:w-[54%] lg:-translate-y-1/2"
          style={{ backgroundImage: `url(${ilustracion})` }}
        />
      )}
      <div className="mx-auto max-w-[1440px] px-pagina">
        {lado ? (
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-16">
            {bloqueTitulo}
            {lado}
          </div>
        ) : (
          bloqueTitulo
        )}
        {children}
      </div>
    </section>
  );
}
