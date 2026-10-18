import Image from 'next/image';
import { botonClases } from '@/components/ui/variantes';
import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';
import { hrefSede } from '@/lib/routes';

type HubGridSedesProps = {
  lang: Locale;
  sedes: SedeContenido[];
  copy: Dictionary['hub'];
};

/**
 * Respaldo accesible/SEO del mapa (spec §5.3): las mismas sedes en tarjetas
 * normales, sin depender de JS ni de interaccion con el SVG.
 */
export function HubGridSedes({ lang, sedes, copy }: HubGridSedesProps) {
  return (
    <div className="scroll-mt-24 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {sedes.map((sede) => (
        <article
          key={sede.slug}
          className="flex flex-col overflow-hidden rounded-card border border-border bg-card"
        >
          <div className="relative h-48 w-full">
            {sede.hero.imagen && (
              <Image
                src={sede.hero.imagen}
                alt={sede.nombre}
                fill
                sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                className="object-cover"
              />
            )}
          </div>
          <div className="flex flex-1 flex-col gap-2 p-6">
            <h3 className="text-xl font-bold text-foreground">
              {sede.nombre}
            </h3>
            {sede.empresaFundadoraNombre && (
              <p className="text-sm text-muted">
                {copy.conLabel} {sede.empresaFundadoraNombre}
              </p>
            )}
            <Link
              href={hrefSede(lang, sede.slug)}
              className={`mt-4 w-fit ${botonClases({ variante: 'principal' })}`}
            >
              {copy.verDestino}
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
