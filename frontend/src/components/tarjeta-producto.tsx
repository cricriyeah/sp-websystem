import Image from 'next/image';
import Link from 'next/link';
import { Check, Clock, UserCircle, UsersThree } from '@phosphor-icons/react/ssr';
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
  /** Ventana de salida («5:00 - 7:00 am»), solo si el servicio pide hora. */
  horario?: string | null;
  /** Los primeros renglones de lo que incluye (máx. 3); solo los muestra la tarjeta única. */
  incluye?: string[];
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
  /** Rótulo de la lista de lo que incluye (tarjeta única). */
  incluye?: string;
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
  /** Es la única de la fila: en escritorio va a todo el ancho, foto a la izquierda y los datos sobre un panel
   * tintado a la derecha, con lo que incluye. En el teléfono es la misma tarjeta vertical, con lo que incluye. */
  unica?: boolean;
};

/**
 * La tarjeta de «Reserva ahora mismo» (F10), igual para servicio y paquete: foto 4:5 (o un bloque del color
 * de su tipo con su palabra, cuando no hay foto honesta), nombre, quién te lleva, cupo y horario con ícono,
 * descripción, el precio como bloque propio (cifra grande y debajo su base y la otra moneda) y el botón
 * «Reservar →». Toda la tarjeta es un solo enlace. En una fila, las tarjetas cierran a la misma altura y los
 * precios quedan alineados para compararlos.
 *
 * Server Component.
 */
export function TarjetaProducto({ vista, textos, prioridad = false, unica = false }: Props) {
  const { nombre, empresa, color, palabra, foto, fotos, precio, capacidad, descripcion, horario, incluye = [] } = vista;
  const tamanos = unica ? '(min-width: 1024px) 55vw, 90vw' : '(min-width: 1024px) 27vw, 80vw';
  const marco = unica ? 'lg:aspect-auto lg:h-full lg:min-h-[30rem]' : '';
  const datos = [
    { icono: UserCircle, texto: textos.opera.replace('{empresa}', empresa) },
    capacidad ? { icono: UsersThree, texto: textos.hasta.replace('{n}', String(capacidad)) } : null,
    horario ? { icono: Clock, texto: horario } : null,
  ].filter((d): d is { icono: typeof UserCircle; texto: string } => d !== null);
  const conIncluye = unica && incluye.length > 0;

  return (
    <Link
      href={vista.hrefDetalle}
      aria-label={textos.reservarAria.replace('{nombre}', nombre).replace('{empresa}', empresa)}
      className={cn(
        'group rev flex flex-[1_0_clamp(16.25rem,27vw,26.25rem)] snap-start flex-col gap-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring',
        unica && 'lg:grid lg:grid-cols-[55fr_45fr] lg:gap-0 lg:bg-cafe-bruma',
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

      <div className={cn('flex flex-1 flex-col gap-4', unica && 'lg:justify-center lg:gap-6 lg:p-12 xl:p-16')}>
        <p className={cn('text-lg font-semibold leading-snug', unica && 'lg:text-4xl lg:leading-tight')}>{nombre}</p>

        <ul className="flex flex-wrap gap-x-5 gap-y-2 texto-cuerpo">
          {datos.map(({ icono: Icono, texto }) => (
            <li key={texto} className="flex items-center gap-2">
              <Icono size={20} weight="regular" aria-hidden="true" className="shrink-0" />
              {texto}
            </li>
          ))}
        </ul>

        {descripcion && <p className={cn('texto-cuerpo max-w-[52ch]', !unica && 'line-clamp-2')}>{descripcion}</p>}

        {conIncluye && (
          <div>
            {textos.incluye && <p className="texto-etiqueta">{textos.incluye}</p>}
            <ul className="mt-3 flex flex-col gap-2 texto-cuerpo">
              {incluye.map((renglon) => (
                <li key={renglon} className="flex items-start gap-2">
                  <Check size={18} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" />
                  {renglon}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className={cn('mt-auto flex flex-wrap items-end justify-between gap-4 pt-2', unica && 'lg:mt-2 lg:justify-start lg:gap-10')}>
          <div className="tabular-nums">
            {precio ? (
              <>
                {precio.conDesde && <span className="block texto-pequeno">{textos.desde}</span>}
                <span className="block text-2xl font-bold leading-tight">{precio.monto}</span>
                <span className="block texto-pequeno">
                  {precio.aprox && `${precio.aprox} · `}
                  {precio.base}
                </span>
              </>
            ) : (
              <span className="block font-semibold">{textos.tarifaRuta}</span>
            )}
          </div>
          <span aria-hidden="true" className={cn(botonClases({ variante: 'campana' }), 'group-hover:bg-cafe max-sm:w-full max-sm:justify-center')}>
            {precio ? textos.reservar : textos.elegirRuta}
            <span className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1">→</span>
          </span>
        </div>
      </div>
    </Link>
  );
}
