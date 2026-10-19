import type { ReactNode } from 'react';

export type Fondo = 'arena' | 'blanco' | 'cafe-bruma';

/**
 * Bandas de sección, alternadas en este orden. `cafe-claro` (amarillo saturado) nunca es
 * fondo de sección. Las clases van completas para que Tailwind las vea.
 */
export const CLASE_FONDO: Record<Fondo, string> = {
  arena: 'bg-background',
  blanco: 'bg-superficie',
  'cafe-bruma': 'bg-cafe-bruma',
};

const ANCHOS_TITULO = {
  '14ch': 'max-w-[14ch]',
  '16ch': 'max-w-[16ch]',
} as const;

type SectionShellProps = {
  /** Ancla de la sección (`#id`); el `<h2>` toma `${id}-titulo` para `aria-labelledby`. */
  id: string;
  fondo: Fondo;
  /** Raya de 1 px arriba: la llevan todas las bandas salvo la primera de la página. */
  borde?: boolean;
  /** Contenido del `<h2>` de la sección. */
  titulo: ReactNode;
  /** Regla de 48 × 2 sobre el título. Por defecto no; máximo 2 por página (`reservar` en la sede, `sedes` en el hub). */
  regla?: boolean;
  /** Ancho máximo del título, en caracteres. Por defecto, 16. */
  anchoTitulo?: keyof typeof ANCHOS_TITULO;
  /** Texto que acompaña al título a su derecha en escritorio (debajo en móvil). */
  lado?: ReactNode;
  /** El contenido llega a sangre, fuera del contenedor, y la sección no deja aire abajo. */
  aSangre?: boolean;
  children: ReactNode;
};

/**
 * Ritmo único de las secciones de una página: fondo, aire vertical, ancho del
 * contenedor, ancla que no queda bajo la cabecera fija (`--nav-alto`) y título
 * `<h2>` enlazado con `aria-labelledby` para que los lectores de pantalla
 * anuncien la sección al llegar por el ancla.
 *
 * Server Component.
 */
export function SectionShell({
  id,
  fondo,
  borde = false,
  titulo,
  regla = false,
  anchoTitulo = '16ch',
  lado,
  aSangre = false,
  children,
}: SectionShellProps) {
  const idTitulo = `${id}-titulo`;
  const bloqueTitulo = (
    <>
      {regla ? <span aria-hidden className="mb-6 block h-0.5 w-12 bg-cafe-medio" /> : null}
      <h2
        id={idTitulo}
        className={`${ANCHOS_TITULO[anchoTitulo]} texto-seccion text-foreground`}
      >
        {titulo}
      </h2>
    </>
  );
  const encabezado = lado ? (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-16">
      <div>{bloqueTitulo}</div>
      {lado}
    </div>
  ) : (
    bloqueTitulo
  );

  return (
    <section
      id={id}
      aria-labelledby={idTitulo}
      className={`scroll-mt-[calc(var(--nav-alto)+16px)] ${CLASE_FONDO[fondo]} ${borde ? 'border-t border-borde ' : ''}${
        aSangre ? 'pt-12 sm:pt-16 lg:pt-24' : 'py-12 sm:py-16 lg:py-24'
      }`}
    >
      {aSangre ? (
        <>
          <div className="mx-auto max-w-[1120px] px-4 pb-10 sm:px-6 lg:px-8 lg:pb-14">{encabezado}</div>
          {children}
        </>
      ) : (
        <div className="mx-auto max-w-[1120px] px-4 sm:px-6 lg:px-8">
          {encabezado}
          {children}
        </div>
      )}
    </section>
  );
}
