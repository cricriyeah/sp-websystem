import Image from 'next/image';
import Link from 'next/link';
import type { Chip } from '@/lib/etiquetas-catalogo';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Lo que pinta cada cortina, ya proyectado en la página (las sedes completas no llegan aquí). */
export type VistaSedeHub = {
  slug: string;
  nombre: string;
  href: string;
  /** Solo si TODAS las sedes tienen foto propia (`tarjetasConFoto`); sin ella la cortina es un campo oscuro. */
  foto: { src: string; alt: string } | null;
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
 * siguiente sube y la cubre. Un espacio de 35 svh entre cortinas da tiempo de leer la sede y de
 * tocar su botón antes de que la cubran; el nombre y el botón van a media altura, no pegados al
 * borde. En móvil son el selector de sede (el mapa es solo de escritorio).
 *
 * Server Component, solo CSS (`position: sticky`).
 */
export function CortinasSedes({ sedes, textos }: Props) {
  return (
    <div className="pb-[35svh]">
      {sedes.map((sede, i) => (
        <article
          key={sede.slug}
          className={cn(
            'group sticky top-[var(--nav-alto)] h-[calc(100svh-var(--nav-alto))] min-h-[32rem] overflow-hidden bg-tinta text-hero-ink',
            i > 0 && 'mt-[35svh]',
          )}
        >
          {sede.foto && (
            <Image
              src={sede.foto.src}
              alt={sede.foto.alt}
              fill
              sizes="100vw"
              loading="lazy"
              className="object-cover transition-transform duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.03]"
            />
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
                <p className="max-w-[40ch] text-xl leading-snug">
                  {sede.chips.length > 0 && <span>{sede.chips.map((chip) => chip.texto).join(' · ')}</span>}
                  {sede.desde && (
                    <span className="block tabular-nums">
                      {textos.desde} <strong>{sede.desde.monto}</strong>
                      {sede.desde.aprox && <span> ({sede.desde.aprox})</span>} {sede.desde.base}
                    </span>
                  )}
                </p>
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
