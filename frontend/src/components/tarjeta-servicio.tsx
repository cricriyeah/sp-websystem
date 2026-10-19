import Image from 'next/image';
import Link from 'next/link';
import { Check } from '@phosphor-icons/react/ssr';
import type { Chip } from '@/lib/etiquetas-catalogo';
import { Card } from '@/components/ui/card';
import { ChipActividad } from '@/components/ui/chip-actividad';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Lo mínimo que la tarjeta pinta. Lo arma `QuePuedesReservar` en servidor: nada de la API completa llega aquí. */
export type VistaTarjeta = {
  clave: string;
  nombre: string;
  empresa: { nombre: string; logo?: string };
  chip: Chip | null;
  foto: { src: string; alt: string } | null;
  /** `null` = por ruta: no hay un monto que anunciar. */
  precio: { monto: string; base: string; conDesde: boolean; aprox?: string } | null;
  capacidad: number | null;
  incluye: string[];
  hrefDetalle: string;
};

export type TextosTarjeta = {
  opera: string;
  incluye: string;
  mas: string;
  preguntaIncluye: string;
  desde: string;
  hasta: string;
  tarifaRuta: string;
  verYReservar: string;
  elegirRuta: string;
  verYReservarAria: string;
};

type Props = {
  vista: VistaTarjeta;
  textos: TextosTarjeta;
  /** «Pregunta qué incluye» lleva aquí cuando hay WhatsApp; sin él queda como texto. */
  hrefContacto: string | null;
  /** La primera del grupo en una plantilla con destacada: «Incluye» va en una columna lateral. */
  destacada?: 'horizontal' | 'lateral';
  /** Las dos primeras fotos de la sección cargan de inmediato; el resto, al acercarse. */
  prioridad?: boolean;
  sizes: string;
  className?: string;
};

const MAX_INCLUYE = 3;

/**
 * La tarjeta de «Qué puedes reservar», la misma para servicio y paquete: foto, chip, nombre,
 * quién lo opera, qué incluye, precio y un solo enlace a su página. Toda la tarjeta es clicable
 * (enlace estirado); el enlace de «Pregunta qué incluye» queda encima.
 *
 * Server Component.
 */
export function TarjetaServicio({ vista, textos, hrefContacto, destacada, prioridad = false, sizes, className }: Props) {
  const { nombre, empresa, chip, foto, precio, capacidad, incluye } = vista;
  const visibles = incluye.slice(0, MAX_INCLUYE);
  const restantes = incluye.length - visibles.length;
  const horizontal = destacada === 'horizontal';

  const bloqueIncluye = (
    <div>
      <p className="texto-pequeno font-semibold text-foreground">{textos.incluye}</p>
      {visibles.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1.5">
          {visibles.map((renglon) => (
            <li key={renglon} className="flex items-start gap-2 texto-pequeno text-foreground">
              <Check size={16} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" />
              <span>{renglon}</span>
            </li>
          ))}
          {restantes > 0 && <li className="texto-pequeno text-muted">{textos.mas.replace('{n}', String(restantes))}</li>}
        </ul>
      ) : hrefContacto ? (
        <a href={hrefContacto} target="_blank" rel="noopener noreferrer" className="relative z-10 mt-2 inline-flex min-h-11 items-center texto-pequeno text-cafe">
          {textos.preguntaIncluye}
        </a>
      ) : (
        <p className="mt-2 texto-pequeno text-muted">{textos.preguntaIncluye}</p>
      )}
    </div>
  );

  return (
    <Card
      plana
      className={cn(
        'group relative flex flex-col overflow-hidden p-0 transition-[border-color,transform] duration-150 active:scale-[0.99] motion-reduce:active:scale-100',
        '[@media(hover:hover)]:hover:border-borde-control has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-ring',
        horizontal && 'sm:flex-row',
        className,
      )}
    >
      {/* Capa de hover: solo con puntero, sobre toda la tarjeta y sin bloquear los clics. */}
      <span aria-hidden="true" className="pointer-events-none absolute inset-0 z-[1] bg-[var(--capa-hover)] opacity-0 transition-opacity duration-150 [@media(hover:hover)]:group-hover:opacity-100" />
      {foto && (
        <div className={cn('relative aspect-[16/10] w-full shrink-0 overflow-hidden', horizontal && 'sm:aspect-auto sm:w-2/5')}>
          <Image src={foto.src} alt={foto.alt} fill sizes={sizes} loading={prioridad ? 'eager' : 'lazy'} className="object-cover" />
        </div>
      )}

      <div className={cn('flex flex-1 flex-col gap-4 p-6', destacada === 'lateral' && 'lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,16rem)] lg:gap-x-8')}>
        <div className="flex flex-col gap-4">
          {chip && (
            <div>
              <ChipActividad tipo={chip.tipo} icono={chip.icono}>{chip.texto}</ChipActividad>
            </div>
          )}
          <h4 className="texto-paso text-foreground">{nombre}</h4>
          <p className="flex items-center gap-2 texto-pequeno font-semibold text-tinta-suave">
            <span aria-hidden="true" className="inline-flex">
              <EmpresaSello nombre={empresa.nombre} logo={empresa.logo} tamano={24} />
            </span>
            {textos.opera.replace('{empresa}', empresa.nombre)}
          </p>
          {destacada !== 'lateral' && bloqueIncluye}
        </div>
        {destacada === 'lateral' && <div className="lg:row-span-2">{bloqueIncluye}</div>}

        <div className="mt-auto flex flex-col gap-4 pt-2">
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2 font-display">
            {precio ? (
              <div>
                <p className="flex flex-wrap items-baseline gap-x-1.5">
                  {precio.conDesde && <span className="texto-pequeno text-muted">{textos.desde}</span>}
                  <span className="text-xl font-bold tabular-nums text-foreground">{precio.monto}</span>
                  <span className="texto-pequeno text-muted">{precio.base}</span>
                </p>
                {precio.aprox && <p className="texto-pequeno tabular-nums text-muted">{precio.aprox}</p>}
              </div>
            ) : (
              <p className="text-base font-semibold text-foreground">{textos.tarifaRuta}</p>
            )}
            {capacidad && <p className="texto-pequeno text-muted">{textos.hasta.replace('{n}', String(capacidad))}</p>}
          </div>
          <Link
            href={vista.hrefDetalle}
            aria-label={textos.verYReservarAria.replace('{nombre}', nombre).replace('{empresa}', empresa.nombre)}
            className={cn(botonClases({ variante: 'secundario' }), 'self-start after:absolute after:inset-0 after:z-[2] after:content-[""] focus-visible:outline-none')}
          >
            {precio ? textos.verYReservar : textos.elegirRuta}
          </Link>
        </div>
      </div>
    </Card>
  );
}
