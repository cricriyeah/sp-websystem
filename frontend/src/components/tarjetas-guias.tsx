import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react/ssr';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Guia, TemaGuia } from '@/content/guias';
import { partesDeTitulo } from '@/content/guias';
import { hrefGuia } from '@/lib/routes';
import { cn } from '@/components/ui/cn';

type Props = {
  lang: Locale;
  guias: readonly Guia[];
  className?: string;
};

// La marca de color de cada tarjeta, en el tono claro de su tema: va sobre la foto oscurecida, donde el tono vivo del
// verde y del azul no se distinguen. Clases completas para que Tailwind las vea.
const MARCA: Record<TemaGuia, string> = { mar: 'bg-azul-medio', traslado: 'bg-coral-medio', estancia: 'bg-verde-claro' };

/**
 * Guías como tarjetas de foto: la foto de la guía llena la tarjeta y el título va encima, abajo, con la flecha que se
 * corre al pasar el cursor mientras la foto se acerca. El color del tema es solo la marca junto al título.
 *
 * El acomodo sale del número de guías, para que ninguna quede sola en su renglón: tres (o seis) van de a tres; dos, de
 * a dos; con número impar, la primera ocupa el renglón entero. La usan el índice, el cierre de cada guía y «Antes de
 * venir» de cada sede.
 *
 * Server Component.
 */
export function TarjetasGuias({ lang, guias, className }: Props) {
  const deATres = guias.length % 3 === 0;
  const primeraAncha = !deATres && guias.length % 2 === 1;

  return (
    <ul className={cn('grid gap-2 sm:gap-3', deATres ? 'lg:grid-cols-3' : 'sm:grid-cols-2', className)}>
      {guias.map((guia, i) => {
        const textos = guia.textos[lang];
        const { principal, resto } = partesDeTitulo(textos.titulo);
        const ancha = primeraAncha && i === 0;
        return (
          <li key={guia.id} className={ancha ? 'sm:col-span-2' : undefined}>
            <Link
              href={hrefGuia(lang, textos.slug)}
              className={cn(
                'group rev relative flex aspect-[4/3] flex-col justify-end overflow-hidden bg-tinta text-hero-ink focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ring',
                ancha ? 'sm:aspect-[21/9]' : deATres && 'lg:aspect-[4/5]',
              )}
            >
              <Image
                src={guia.foto.src}
                alt=""
                fill
                sizes={ancha ? '(min-width: 1440px) 1306px, 100vw' : deATres ? '(min-width: 1024px) 34vw, 100vw' : '(min-width: 640px) 50vw, 100vw'}
                className="object-cover transition-transform duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.04]"
              />
              <span aria-hidden="true" className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />
              <span className="relative flex items-end justify-between gap-5 p-5 sm:p-6">
                <span className="flex items-stretch gap-4">
                  <span aria-hidden="true" className={cn('w-1.5 shrink-0', MARCA[guia.tema])} />
                  <span className="flex flex-col gap-1.5">
                    <strong className="texto-paso">{principal}</strong>
                    {resto && <span className="texto-cuerpo leading-snug">{resto}</span>}
                  </span>
                </span>
                <ArrowRight
                  size={28}
                  weight="bold"
                  aria-hidden="true"
                  className="mb-1 shrink-0 transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1.5"
                />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
