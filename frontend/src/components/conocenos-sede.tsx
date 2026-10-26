import Image from 'next/image';
import type { SedeConocenos } from '@/content/sedes-tipos';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

type Props = {
  id: string;
  conocenos: SedeConocenos;
  fondo: Fondo;
};

/** Columnas de la tira de fotos según cuántas haya (clases completas para que Tailwind las vea). */
const COLUMNAS_TIRA: Record<number, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-2',
  3: 'grid-cols-2 sm:grid-cols-3',
};

/**
 * «Conócenos» como portada: la primera foto a todo lo ancho con «Desde 1950» y el título encima. Si la sede
 * tiene más fotos, van en una tira debajo. El contenido es de `sedes-cuerpo`: solo La Paz lo tiene hoy y sin él
 * la sección no se pinta (`seccionesDeSede`).
 *
 * Server Component.
 */
export function ConocenosSede({ id, conocenos, fondo }: Props) {
  const [principal, ...resto] = conocenos.fotos;
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-12">
        <div className="relative aspect-[4/5] overflow-hidden bg-tinta text-hero-ink sm:aspect-[16/9] lg:aspect-[21/9]">
          {principal && <Image src={principal.src} alt={principal.alt} fill sizes="100vw" className="rev-foto object-cover object-top" />}
          <div aria-hidden="true" className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />
          <div className="absolute inset-x-0 bottom-0 flex flex-col gap-4 p-5 sm:p-8 lg:flex-row lg:items-end lg:justify-between lg:p-12">
            <p className="rev flex flex-col gap-2 text-cafe-claro">
              <span className="texto-grande">{conocenos.etiquetaDesde}</span>
              <span className="texto-gigante tabular-nums">{conocenos.desde}</span>
            </p>
            <h2 id={`${id}-titulo`} className="rev max-w-[18ch] texto-seccion lg:pb-6 lg:text-right">{conocenos.titulo}</h2>
          </div>
        </div>
        {resto.length > 0 && (
          <div className={cn('mt-3 grid gap-3 sm:mt-4 sm:gap-4', resto.length >= 4 ? 'grid-cols-2 sm:grid-cols-4' : COLUMNAS_TIRA[resto.length])}>
            {resto.map((foto) => (
              <div key={foto.src} className="rev-foto relative aspect-[4/3] overflow-hidden bg-cafe-bruma">
                <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 640px) 25vw, 50vw" className="object-cover" />
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
