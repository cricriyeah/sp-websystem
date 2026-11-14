import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react/ssr';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Guia } from '@/content/guias';
import { hrefGuia } from '@/lib/routes';
import { cn } from '@/components/ui/cn';

type Props = {
  lang: Locale;
  guias: readonly Guia[];
  /** El tono del bloque de cada guía: un paso distinto del fondo de la sección, como las preguntas frecuentes. */
  bloque: 'bg-cafe-bruma' | 'bg-superficie';
  /** Bajo el título, la frase que dice qué contesta la guía (su descripción). Para el índice, donde se escoge una. */
  resumen?: boolean;
  /**
   * En columnas desde escritorio, para una fila corta que ocupa todo el ancho de la página (la de una sede): tres por
   * renglón si son tres (o seis), dos si no, para que ninguna quede sola.
   */
  columnas?: boolean;
  className?: string;
};

/**
 * Enlaces a guías como bloques rectos, con la misma forma que las preguntas frecuentes: el título dice a dónde lleva y
 * la flecha se corre al pasar el cursor. La usan el índice, el cierre de cada guía y la fila «Antes de venir» de cada
 * sede.
 *
 * Server Component.
 */
export function ListaGuias({ lang, guias, bloque, resumen = false, columnas = false, className }: Props) {
  return (
    <ul className={cn(columnas ? ['grid gap-2', guias.length % 3 === 0 ? 'lg:grid-cols-3' : 'lg:grid-cols-2'] : 'flex flex-col gap-2', className)}>
      {guias.map((guia) => {
        const textos = guia.textos[lang];
        return (
          <li key={guia.id} className={columnas ? 'flex' : undefined}>
            <Link
              href={hrefGuia(lang, textos.slug)}
              className={cn(
                'group flex min-h-[4.5rem] w-full items-center justify-between gap-6 px-6 py-5 transition-colors duration-200 focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ring',
                bloque,
              )}
            >
              <span className="flex flex-col gap-2">
                <span className="text-xl font-semibold leading-snug transition-colors group-hover:text-cafe">{textos.titulo}</span>
                {resumen && <span className="max-w-[60ch] texto-cuerpo">{textos.metaDescripcion}</span>}
              </span>
              <ArrowRight
                size={28}
                weight="bold"
                aria-hidden="true"
                className="shrink-0 transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1.5"
              />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
