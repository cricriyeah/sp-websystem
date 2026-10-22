import Image from 'next/image';
import Link from 'next/link';
import type { ColorActividad } from '@/lib/color-actividad';
import { CarruselFotos } from '@/components/carrusel-fotos';
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
  /** Dos o tres frases de venta (`content/descripciones-catalogo.ts`); sin ella no se pinta. */
  descripcion?: string | null;
  foto: { src: string; alt: string } | null;
  /** Todas sus fotos, si son varias: la tarjeta las cambia como carrusel. */
  fotos?: { src: string; alt: string }[];
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

/** Un desfase estable (0 a 1,5 s) por tarjeta, sacado de su clave: sin azar, para que servidor y cliente coincidan. */
export function desfaseDe(clave: string): number {
  let h = 0;
  for (const c of clave) h = (h * 31 + c.charCodeAt(0)) % 1500;
  return h;
}

type Props = {
  vista: VistaProducto;
  textos: TextosProducto;
  /** Las dos primeras fotos de la fila cargan de inmediato; el resto, al acercarse. */
  prioridad?: boolean;
  /** Es la única de la fila: en escritorio va horizontal (foto a la izquierda, datos a la derecha) en vez de
   * estirarse a todo el ancho con la foto vertical. En el teléfono no cambia. */
  unica?: boolean;
};

/**
 * La tarjeta de «Qué puedes reservar» (F10), igual para servicio y paquete: foto 4:5 (o un bloque del color
 * de su tipo con su palabra, cuando no hay foto honesta), nombre, quién lo opera, precio y un botón
 * «Reservar →». Toda la tarjeta es un solo enlace. Crece hasta llenar la fila si caben todas; sola, en
 * escritorio se pone horizontal.
 *
 * Server Component.
 */
export function TarjetaProducto({ vista, textos, prioridad = false, unica = false }: Props) {
  const { nombre, empresa, color, palabra, foto, fotos, precio, capacidad, descripcion } = vista;
  const tamanos = unica ? '(min-width: 1024px) 42vw, 80vw' : '(min-width: 1024px) 27vw, 80vw';
  const marco = unica ? 'lg:aspect-[4/3] lg:w-[42%] lg:shrink-0' : '';
  const info = [textos.opera.replace('{empresa}', empresa), capacidad ? textos.hasta.replace('{n}', String(capacidad)) : null].filter(Boolean).join(' · ');

  return (
    <Link
      href={vista.hrefDetalle}
      aria-label={textos.reservarAria.replace('{nombre}', nombre).replace('{empresa}', empresa)}
      className={cn(
        'group rev flex flex-[1_0_clamp(16.25rem,27vw,26.25rem)] snap-start flex-col gap-3.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring',
        unica && 'lg:flex-row lg:items-stretch lg:gap-12',
      )}
    >
      {foto ? (
        <div className={cn('rev-foto relative aspect-[4/5] overflow-hidden bg-cafe-bruma', marco)}>
          {fotos && fotos.length > 1 ? (
            <CarruselFotos
              fotos={fotos}
              sizes={tamanos}
              prioridad={prioridad}
              desfase={desfaseDe(vista.clave)}
              className="[@media(hover:hover)]:group-hover:scale-105"
            />
          ) : (
            <Image
              src={foto.src}
              alt={foto.alt}
              fill
              sizes={tamanos}
              loading={prioridad ? 'eager' : 'lazy'}
              className="object-cover transition-transform duration-[600ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-105"
            />
          )}
        </div>
      ) : (
        <div aria-hidden="true" className={cn('rev-foto grid aspect-[4/5] place-items-center overflow-hidden p-6 text-center', CAMPO[color], marco)}>
          <span className="texto-seccion block transition-transform duration-[400ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:-translate-y-1.5">
            {palabra}
          </span>
        </div>
      )}
      <div className={cn('flex flex-1 flex-col gap-3.5', unica && 'lg:justify-center lg:gap-5 lg:py-6')}>
      <p className={cn('text-lg font-semibold leading-snug', unica && 'lg:text-4xl lg:leading-tight')}>{nombre}</p>
      <p className="texto-cuerpo">{info}</p>
      {descripcion && <p className={cn('texto-cuerpo max-w-[52ch]', !unica && 'line-clamp-3')}>{descripcion}</p>}
      <div className={cn('mt-auto flex flex-wrap items-center justify-between gap-3', unica && 'lg:mt-4 lg:justify-start lg:gap-8')}>
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
        <span aria-hidden="true" className={cn(botonClases({ variante: 'campana' }), 'group-hover:bg-cafe max-sm:w-full max-sm:justify-center')}>
          {precio ? textos.reservar : textos.elegirRuta}
          <span className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1">→</span>
        </span>
      </div>
      </div>
    </Link>
  );
}
