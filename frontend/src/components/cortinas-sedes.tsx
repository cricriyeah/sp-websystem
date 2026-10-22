import { FotosRotativas } from '@/components/fotos-rotativas';
import Link from 'next/link';
import type { Chip } from '@/lib/etiquetas-catalogo';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Lo que pinta cada cortina, ya proyectado en la página (las sedes completas no llegan aquí). */
export type VistaSedeHub = {
  slug: string;
  nombre: string;
  href: string;
  /**
   * Fotos propias de la sede (nunca las del hub), que rotan solas. Solo si TODAS las sedes tienen foto
   * propia (`tarjetasConFoto`); vacías, la cortina es un campo oscuro.
   */
  fotos: { src: string; alt: string }[];
  /** Sin resumen de la API (fallo parcial) van vacíos: la cortina conserva su botón. */
  chips: Chip[];
  empresas: string | null;
  desde: { monto: string; aprox?: string; base: string } | null;
};

type Props = {
  sedes: VistaSedeHub[];
  textos: { region: string; desde: string; verSede: string };
};

/**
 * Las sedes como cortinas a pantalla completa (F10): cada una queda fija bajo la barra mientras la
 * siguiente sube y la cubre. Un espacio de 20 svh entre cortinas (no tras la última: ahí empieza la siguiente sección) da tiempo de leer la sede y de
 * tocar su botón antes de que la cubran; el nombre y el botón van a media altura, no pegados al
 * borde. En móvil son el selector de sede (el mapa es solo de escritorio).
 *
 * Server Component (`position: sticky`); las fotos rotan en `FotosRotativas`, del lado del cliente.
 */
export function CortinasSedes({ sedes, textos }: Props) {
  return (
    <div>
      {sedes.map((sede, i) => (
        <article
          key={sede.slug}
          id={`sede-${sede.slug}`}
          className={cn(
            'group sticky top-[var(--nav-alto)] h-[calc(100svh-var(--nav-alto))] min-h-[32rem] scroll-mt-[var(--nav-alto)] overflow-hidden bg-tinta text-hero-ink',
            i > 0 && 'mt-[20svh]',
          )}
        >
          {sede.fotos.length > 0 && (
            <FotosRotativas fotos={sede.fotos} sizes="100vw" />
          )}
          <div aria-hidden="true" className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />
          <div className="relative mx-auto flex h-full w-full max-w-[1440px] flex-col justify-between px-4 pb-[clamp(7.5rem,26svh,17.5rem)] pt-6 sm:px-6 lg:px-12">
            <div className="flex flex-wrap justify-between gap-x-6 gap-y-1 texto-etiqueta">
              <p>{textos.region}</p>
              {sede.empresas && <p>{sede.empresas}</p>}
            </div>
            <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-6">
              <h3 className="texto-gigante">{sede.nombre}</h3>
              <div className="flex flex-col gap-4 sm:items-end sm:text-right">
                <div className="flex max-w-[40ch] flex-col gap-2 sm:items-end">
                  {sede.chips.length > 0 && <p className="text-xl leading-snug">{sede.chips.map((chip) => chip.texto).join(' · ')}</p>}
                  {sede.desde && (
                    <p className="tabular-nums">
                      <span className="block texto-cuerpo">{textos.desde}</span>
                      <span className="block text-3xl font-bold leading-tight">{sede.desde.monto}</span>
                      <span className="block texto-cuerpo">
                        {sede.desde.aprox && `${sede.desde.aprox} · `}
                        {sede.desde.base}
                      </span>
                    </p>
                  )}
                </div>
                <Link href={sede.href} className={cn(botonClases({ variante: 'campana-claro' }), 'self-start sm:self-end')}>
                  {textos.verSede.replace('{sede}', sede.nombre)}
                </Link>
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
