import Image from 'next/image';
import Link from 'next/link';
import type { Chip } from '@/lib/etiquetas-catalogo';
import { Card } from '@/components/ui/card';
import { ChipActividad } from '@/components/ui/chip-actividad';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Lo que pinta la tarjeta, ya proyectado en la página (las sedes completas no llegan aquí). */
export type VistaSedeHub = {
  slug: string;
  nombre: string;
  href: string;
  /** Solo si TODAS las sedes tienen foto propia (`tarjetasConFoto`). */
  foto: { src: string; alt: string } | null;
  /** Sin resumen de la API (fallo parcial) van vacíos: la tarjeta conserva su alto y su CTA. */
  chips: Chip[];
  empresas: string | null;
  desde: { monto: string; aprox?: string; base: string } | null;
};

type Props = {
  vista: VistaSedeHub;
  textos: { region: string; desde: string; verSede: string };
  /** 768-1279 px con 3 sedes: la tercera ocupa las dos columnas en horizontal. */
  horizontalEnMd?: boolean;
  className?: string;
};

/**
 * Tarjeta de sede del hub: qué se puede hacer, quién opera y desde cuánto. Toda la tarjeta
 * es clicable (enlace estirado); hover solo con puntero.
 *
 * Server Component.
 */
export function TarjetaSedeHub({ vista, textos, horizontalEnMd = false, className }: Props) {
  const { nombre, foto, chips, empresas, desde } = vista;
  return (
    <Card
      plana
      className={cn(
        'group relative flex h-full flex-col overflow-hidden p-0 transition-[border-color,transform] duration-150 active:scale-[0.99] motion-reduce:active:scale-100',
        '[@media(hover:hover)]:hover:border-borde-control has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-ring',
        horizontalEnMd && foto && 'md:flex-row xl:flex-col',
        className,
      )}
    >
      <span aria-hidden="true" className="pointer-events-none absolute inset-0 z-[1] bg-[var(--capa-hover)] opacity-0 transition-opacity duration-150 [@media(hover:hover)]:group-hover:opacity-100" />
      {foto && (
        <div className={cn('relative aspect-[16/9] w-full shrink-0 md:aspect-[16/10]', horizontalEnMd && 'md:aspect-auto md:w-1/2 xl:aspect-[16/10] xl:w-full')}>
          <Image src={foto.src} alt={foto.alt} fill sizes="(min-width: 1280px) 33vw, (min-width: 768px) 50vw, 100vw" className="object-cover" />
        </div>
      )}
      <div className="flex flex-1 flex-col gap-3 p-6">
        {!foto && <p className="texto-pequeno font-semibold text-muted">{textos.region}</p>}
        <h3 className="texto-paso text-foreground">{nombre}</h3>
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {chips.map((chip) => (
              <ChipActividad key={chip.texto} tipo={chip.tipo} icono={chip.icono}>{chip.texto}</ChipActividad>
            ))}
          </div>
        )}
        {empresas && <p className="texto-pequeno text-tinta-suave">{empresas}</p>}
        {desde && (
          <div className="font-display">
            <p className="flex flex-wrap items-baseline gap-x-1.5">
              <span className="texto-pequeno text-muted">{textos.desde}</span>
              <span className="text-xl font-bold tabular-nums text-foreground">{desde.monto}</span>
              {desde.aprox && <span className="texto-pequeno tabular-nums text-muted">({desde.aprox})</span>}
              <span className="texto-pequeno text-muted">{desde.base}</span>
            </p>
          </div>
        )}
        <Link
          href={vista.href}
          className={cn(botonClases({ variante: 'secundario', bloque: true }), 'mt-auto min-h-12 after:absolute after:inset-0 after:z-[2] after:content-[""] focus-visible:outline-none')}
        >
          {textos.verSede.replace('{sede}', nombre)}
        </Link>
      </div>
    </Card>
  );
}
