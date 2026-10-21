import type { ReactNode } from 'react';

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

type SectionShellProps = {
  /** Ancla de la sección (`#id`); el `<h2>` toma `${id}-titulo` para `aria-labelledby`. */
  id: string;
  fondo: Fondo;
  /** Contenido del `<h2>` de la sección. */
  titulo: ReactNode;
  /** Ancho máximo del título, en caracteres. Por defecto, 24. */
  anchoTitulo?: keyof typeof ANCHOS_TITULO;
  /** Texto que acompaña al título a su derecha en escritorio (debajo en móvil). */
  lado?: ReactNode;
  children: ReactNode;
};

/**
 * Ritmo único de las secciones de una página: banda de color (sin rayas), aire vertical, contenedor
 * de 1440 px con el margen de la página, ancla que no queda bajo la cabecera fija (`--nav-alto`) y
 * título `<h2>` enlazado con `aria-labelledby` para que los lectores de pantalla anuncien la sección
 * al llegar por el ancla. El título sube al entrar (`rev`).
 *
 * Server Component.
 */
export function SectionShell({ id, fondo, titulo, anchoTitulo = '24ch', lado, children }: SectionShellProps) {
  const idTitulo = `${id}-titulo`;
  const bloqueTitulo = <h2 id={idTitulo} className={`rev ${ANCHOS_TITULO[anchoTitulo]} texto-seccion`}>{titulo}</h2>;

  return (
    <section
      id={id}
      aria-labelledby={idTitulo}
      className={`scroll-mt-[calc(var(--nav-alto)+16px)] ${CLASE_FONDO[fondo]} py-16 sm:py-20 lg:py-28`}
    >
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-12">
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
