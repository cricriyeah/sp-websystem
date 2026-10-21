import Image from 'next/image';
import Link from 'next/link';
import type { ColorActividad } from '@/lib/color-actividad';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Lo mínimo que la tarjeta pinta. Lo arma `QuePuedesReservar` en servidor: nada de la API completa llega aquí. */
export type VistaProducto = {
  clave: string;
  nombre: string;
  empresa: string;
  color: ColorActividad;
  /** La palabra del tipo («Pesca», «5 noches»): rotula el bloque de color cuando no hay foto honesta. */
  palabra: string;
  foto: { src: string; alt: string } | null;
  /** `null` = por ruta: no hay un monto que anunciar. */
  precio: { monto: string; base: string; conDesde: boolean; aprox?: string } | null;
  capacidad: number | null;
  hrefDetalle: string;
};

export type TextosProducto = {
  opera: string;
  desde: string;
  hasta: string;
  tarifaRuta: string;
  reservar: string;
  elegirRuta: string;
  reservarAria: string;
};

// Clases completas para que Tailwind las vea. Azul = mar, coral = traslados, verde = estancia.
const CAMPO: Record<ColorActividad, string> = {
  mar: 'bg-azul text-white',
  traslado: 'bg-coral text-white',
  estancia: 'bg-verde text-white',
};

type Props = {
  vista: VistaProducto;
  textos: TextosProducto;
  /** Las dos primeras fotos de la fila cargan de inmediato; el resto, al acercarse. */
  prioridad?: boolean;
};

/**
 * La tarjeta de «Qué puedes reservar» (F10), igual para servicio y paquete: foto 4:5 (o un bloque del color
 * de su tipo con su palabra, cuando no hay foto honesta), nombre, quién lo opera, precio y un botón
 * «Reservar →». Toda la tarjeta es un solo enlace. Crece hasta llenar la fila si caben todas.
 *
 * Server Component.
 */
export function TarjetaProducto({ vista, textos, prioridad = false }: Props) {
  const { nombre, empresa, color, palabra, foto, precio, capacidad } = vista;
  const info = [textos.opera.replace('{empresa}', empresa), capacidad ? textos.hasta.replace('{n}', String(capacidad)) : null].filter(Boolean).join(' · ');

  return (
    <Link
      href={vista.hrefDetalle}
      aria-label={textos.reservarAria.replace('{nombre}', nombre).replace('{empresa}', empresa)}
      className="group rev flex flex-[1_0_clamp(16.25rem,27vw,26.25rem)] snap-start flex-col gap-3.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
    >
      {foto ? (
        <div className="rev-foto relative aspect-[4/5] overflow-hidden bg-cafe-bruma">
          <Image
            src={foto.src}
            alt={foto.alt}
            fill
            sizes="(min-width: 1024px) 27vw, 80vw"
            loading={prioridad ? 'eager' : 'lazy'}
            className="object-cover transition-transform duration-[600ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-105"
          />
        </div>
      ) : (
        <div aria-hidden="true" className={cn('rev-foto grid aspect-[4/5] place-items-center overflow-hidden p-6 text-center', CAMPO[color])}>
          <span className="texto-seccion block transition-transform duration-[400ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:-translate-y-1.5">
            {palabra}
          </span>
        </div>
      )}
      <p className="text-lg font-semibold leading-snug">{nombre}</p>
      <p className="texto-cuerpo">{info}</p>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
        <p className="font-semibold tabular-nums">
          {precio ? (
            <>
              {precio.conDesde && <span className="font-normal">{textos.desde} </span>}
              {precio.monto} <span className="font-normal">{precio.base}</span>
              {precio.aprox && <span className="block font-normal">{precio.aprox}</span>}
            </>
          ) : (
            textos.tarifaRuta
          )}
        </p>
        <span aria-hidden="true" className={cn(botonClases({ variante: 'campana' }), 'group-hover:bg-cafe')}>
          {precio ? textos.reservar : textos.elegirRuta}
          <span className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1">→</span>
        </span>
      </div>
    </Link>
  );
}
