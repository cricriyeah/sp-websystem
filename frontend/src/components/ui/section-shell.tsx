import type { ReactNode } from 'react';

type Fondo = 'papel' | 'bruma' | 'bruma-profunda';

/**
 * Hasta F7 la paleta solo admite estos tres fondos; F7 los renombra a
 * `arena | blanco | cafe-bruma`. Las clases van completas para que Tailwind las vea.
 * `bruma-profunda` usa el alias `cafe-claro` (mismo valor que `surface-deep`, ver
 * globals.css) para no sumar un `bg-surface-deep` crudo sin consumidor todavía.
 */
const FONDOS: Record<Fondo, string> = {
  papel: 'bg-background',
  bruma: 'bg-surface',
  'bruma-profunda': 'bg-cafe-claro',
};

const ANCHOS_TITULO = {
  '14ch': 'max-w-[14ch]',
  '16ch': 'max-w-[16ch]',
} as const;

type SectionShellProps = {
  /** Ancla de la sección (`#id`); el `<h2>` toma `${id}-titulo` para `aria-labelledby`. */
  id: string;
  fondo: Fondo;
  /** Contenido del `<h2>` de la sección. */
  titulo: ReactNode;
  /** Regla corta de acento sobre el título. Por defecto, sí. */
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
  titulo,
  regla = true,
  anchoTitulo = '16ch',
  lado,
  aSangre = false,
  children,
}: SectionShellProps) {
  const idTitulo = `${id}-titulo`;
  const bloqueTitulo = (
    <>
      {regla ? <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" /> : null}
      <h2
        id={idTitulo}
        className={`${ANCHOS_TITULO[anchoTitulo]} text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]`}
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
      className={`scroll-mt-[calc(var(--nav-alto)+16px)] ${FONDOS[fondo]} ${
        aSangre ? 'pt-24 lg:pt-32' : 'py-24 lg:py-32'
      }`}
    >
      {aSangre ? (
        <>
          <div className="mx-auto max-w-6xl px-6 pb-10 sm:px-8 lg:px-12 lg:pb-14">{encabezado}</div>
          {children}
        </>
      ) : (
        <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
          {encabezado}
          {children}
        </div>
      )}
    </section>
  );
}
