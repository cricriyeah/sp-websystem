import Image from 'next/image';
import Link from 'next/link';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';

type HubGridSedesProps = {
  lang: Locale;
  sedes: SedeContenido[];
  verDestinoLabel: string;
  conLabel: string;
};

/**
 * Respaldo accesible/SEO del mapa (spec §5.3): las mismas sedes en tarjetas
 * normales, sin depender de JS ni de interaccion con el SVG.
 */
export function HubGridSedes({ lang, sedes, verDestinoLabel, conLabel }: HubGridSedesProps) {
  return (
    <div id="sedes" className="scroll-mt-24 grid gap-6 sm:grid-cols-2">
      {sedes.map((sede) => (
        <article
          key={sede.slug}
          className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
        >
          <div className="relative h-48 w-full">
            {sede.hero.imagen && (
              <Image
                src={sede.hero.imagen}
                alt={sede.negocio?.nombre ?? sede.empresaFundadoraNombre}
                fill
                className="object-cover"
              />
            )}
          </div>
          <div className="flex flex-1 flex-col gap-2 p-6">
            <h3 className="text-xl font-bold text-foreground">
              {sede.negocio?.nombre ?? sede.empresaFundadoraNombre}
            </h3>
            <p className="text-sm text-muted">
              {conLabel} {sede.empresaFundadoraNombre}
            </p>
            <Link
              href={`/${lang}/sede/${sede.slug}`}
              className="mt-4 inline-flex w-fit items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-transform hover:brightness-105 active:scale-[0.98]"
            >
              {verDestinoLabel}
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
