import Image from 'next/image';
import Link from 'next/link';
import type { SedeHeroMarca as Marca } from '@/content/sedes-tipos';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

type Props = {
  marca: Marca;
  /** El isotipo de la empresa (pez gallo y sol). Sin él, el nombre va solo. */
  isotipo?: string;
  /** Nombre completo de la empresa: el nombre accesible del monumento. */
  empresa: string;
  cta: string;
};

/**
 * Primera vista «de marca» (dirección de taste «El nombre como monumento», derivación PFD R2): lo primero que se ve es
 * la marca del cliente y una panga suya, no una palabra genérica.
 *
 * Sobre un campo tinta, arriba y a todo el ancho, el nombre como monumento: «Sal y», el isotipo del tamaño de una letra
 * y «Sol» (en el teléfono, «Sal y» en un renglón y el isotipo con «Sol» en el siguiente). Va arriba a propósito: abajo
 * lo taparía el aviso de cookies en la primera visita. Debajo, la foto a sangre de la panga (columnas 6-12 en
 * escritorio, todo el ancho en el teléfono) y, a su izquierda, el `h1` con qué es y dónde, una frase y el único botón.
 *
 * El monumento es una sola etiqueta para los lectores de pantalla (el nombre completo); el `h1` es el título de la
 * página. La foto es el LCP: `loading="eager"` y `fetchPriority="high"` (Next 16 lo recomienda antes que `preload`).
 * Server Component, sin JavaScript de cliente.
 */
export function SedeHeroMarca({ marca, isotipo, empresa, cta }: Props) {
  return (
    <section className="bg-tinta text-hero-ink">
      <div className="mx-auto grid min-h-svh max-w-[1440px] grid-rows-[auto_minmax(15rem,1fr)_auto] gap-x-6 gap-y-6 px-pagina pb-8 pt-[calc(var(--nav-alto)+1.25rem)] sm:pb-10 xl:grid-cols-12 xl:grid-rows-[auto_1fr] xl:gap-y-8">
        <p aria-label={empresa} className="rev texto-marca m-0 flex flex-wrap items-center gap-x-[0.22em] gap-y-[0.04em] xl:col-span-12">
          <span aria-hidden>{marca.nombre.inicio}</span>
          <span aria-hidden className="flex items-center gap-[0.12em]">
            {isotipo && (
              <span className="relative block size-[0.9em] shrink-0 overflow-hidden rounded-full bg-blanco">
                <Image src={isotipo} alt="" fill loading="eager" sizes="(min-width: 1280px) 180px, 25vw" className="object-contain p-[6%]" />
              </span>
            )}
            {marca.nombre.fin}
          </span>
        </p>

        <div className="rev-foto relative overflow-hidden bg-tinta xl:col-span-7 xl:col-start-6 xl:row-start-2">
          <Image
            src={marca.foto.src}
            alt={marca.foto.alt}
            fill
            loading="eager"
            fetchPriority="high"
            sizes="(min-width: 1280px) 66vw, 100vw"
            className="foto-deriva object-cover"
            style={{ objectPosition: marca.foto.posicion }}
          />
        </div>

        <div className="rev flex flex-col gap-4 xl:col-span-5 xl:col-start-1 xl:row-start-2 xl:self-end">
          <h1 className="texto-pagina m-0">{marca.titulo}</h1>
          <p className="m-0 max-w-[44ch] text-lg leading-snug">{marca.frase}</p>
          <Link href={`#${ANCLA_DE.reservar}`} className={cn(botonClases({ variante: 'campana-claro' }), 'self-start')}>
            {cta}
          </Link>
        </div>
      </div>
    </section>
  );
}
