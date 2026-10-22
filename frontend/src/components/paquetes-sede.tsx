import Image from 'next/image';
import Link from 'next/link';
import { Check, UserCircle } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { colorDeServicio } from '@/lib/color-actividad';
import { vistaDePaquete } from '@/components/vistas-catalogo';
import { CarruselFotos } from '@/components/carrusel-fotos';
import { desfaseDe } from '@/components/tarjeta-producto';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

type Textos = Dictionary['sedeContenido']['paquetes'];
type TextosReservar = Dictionary['sedeContenido']['queReservar'];

type Props = {
  id: string;
  lang: Locale;
  moneda: Moneda;
  paquetes: PaqueteCatalogo[];
  textos: Textos;
  textosReservar: TextosReservar;
  fondo: Fondo;
};

// Un renglón de «incluye» que en realidad dice lo que NO incluye: va como nota bajo el precio, sin palomita.
const EXCLUSION = /no incluye|not include/i;
// El renglón de los días en el mar («del día 2 al 5»): la franja ya lo dice.
const RENGLON_DIAS = /d[ií]a \d+ al \d+|day \d+ to (day )?\d+/i;
// Renglones de «incluye» por tarjeta: 4 en escritorio, 3 en el teléfono. La lista completa está en el detalle.
const MAX_INCLUYE = 4;

/**
 * Los días de la estancia: llega el día 1, sale al mar del día 2 a la última noche y se va el día siguiente.
 * Es la regla de los paquetes de La Ventana; solo se pinta si el paquete tiene noches y algo de mar.
 */
function franjaDe(paquete: PaqueteCatalogo): { dias: number; marHasta: number } | null {
  const noches = paquete.noches ?? 0;
  const conMar = paquete.servicios_asociados.some((c) => colorDeServicio(c.servicio) === 'mar');
  return noches >= 2 && conMar ? { dias: noches + 1, marHasta: noches } : null;
}

/**
 * Los paquetes de la sede, cada uno en una tarjeta con foto. La cifra de noches manda (es lo que distingue un
 * paquete del otro); debajo, los días en la sede, quién te lleva, la franja de días (llegada, mar, salida), lo
 * que incluye y el precio con «Reservar →». Lo que el paquete no incluye va como nota bajo el precio. La foto
 * va siempre del mismo lado para que las tarjetas se comparen renglón con renglón. Toda la tarjeta es un solo
 * enlace a la página del paquete; ahí está el nombre del backoffice y la lista completa.
 *
 * Server Component.
 */
export function PaquetesSede({ id, lang, moneda, paquetes, textos, textosReservar, fondo }: Props) {
  // El paso de tono: la tarjeta es gris sobre blanco y blanca sobre gris.
  const tarjeta = fondo === 'cafe-bruma' ? 'bg-superficie' : 'bg-cafe-bruma';

  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
      <div className="mt-10 flex flex-col gap-4">
        {paquetes.map((paquete, i) => {
          const vista = vistaDePaquete(paquete, lang, moneda);
          const franja = franjaDe(paquete);
          const renglones = paquete.incluye?.[lang] ?? [];
          const exclusiones = renglones.filter((r) => EXCLUSION.test(r));
          const incluye = renglones
            .filter((r) => !EXCLUSION.test(r) && !(franja && RENGLON_DIAS.test(r)))
            .slice(0, MAX_INCLUYE);
          const porGrupo =
            paquete.estrategia_precio === 'por_grupo' ? textos.incluyePersonas.replace('{n}', String(paquete.personas_precio_base)) : null;
          return (
            <Link
              key={paquete.slug}
              href={vista.hrefDetalle}
              aria-label={textosReservar.verYReservarAria.replace('{nombre}', vista.nombre).replace('{empresa}', vista.empresa)}
              className={cn('group rev grid focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring md:grid-cols-[1.1fr_1fr]', tarjeta)}
            >
              <div
                className={cn(
                  'relative aspect-[4/3] overflow-hidden md:aspect-auto md:min-h-[clamp(22.5rem,40vw,35rem)]',
                  !vista.foto && 'grid place-items-center bg-verde p-6 text-center text-white',
                )}
              >
                {vista.fotos && vista.fotos.length > 1 ? (
                  <CarruselFotos
                    fotos={vista.fotos}
                    sizes="(min-width: 768px) 55vw, 100vw"
                    prioridad={i === 0}
                    desfase={desfaseDe(vista.clave)}
                    className="[@media(hover:hover)]:group-hover:scale-[1.04]"
                  />
                ) : vista.foto ? (
                  <Image
                    src={vista.foto.src}
                    alt={vista.foto.alt}
                    fill
                    sizes="(min-width: 768px) 55vw, 100vw"
                    loading={i === 0 ? 'eager' : 'lazy'}
                    className="object-cover transition-transform duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.04]"
                  />
                ) : (
                  <span aria-hidden="true" className="texto-seccion">{vista.palabra}</span>
                )}
              </div>

              <div className="flex flex-col gap-7 p-6 sm:p-8 lg:p-12">
                <div>
                  <h3 className="texto-grande">{paquete.noches ? textos.noches.replace('{n}', String(paquete.noches)) : vista.nombre}</h3>
                  {paquete.noches ? (
                    <p className="mt-3 texto-subtitulo">{textos.dias.replace('{n}', String(paquete.noches + 1)).replace('{sede}', paquete.sede)}</p>
                  ) : null}
                  <p className="mt-3 flex items-center gap-2 texto-cuerpo">
                    <UserCircle size={20} weight="regular" aria-hidden="true" className="shrink-0" />
                    {textosReservar.opera.replace('{empresa}', vista.empresa)}
                  </p>
                </div>

                {franja && (
                  <div>
                    <div aria-hidden="true" className="flex gap-1">
                      {Array.from({ length: franja.dias }, (_, d) => d + 1).map((dia) => (
                        <span
                          key={dia}
                          className={cn(
                            'grid h-10 flex-1 place-items-center texto-pequeno font-semibold tabular-nums text-white',
                            dia === 1 || dia === franja.dias ? 'bg-verde' : 'bg-azul',
                          )}
                        >
                          {dia}
                        </span>
                      ))}
                    </div>
                    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 texto-pequeno">
                      {(
                        [
                          ['bg-verde', textos.llegada],
                          ['bg-azul', textos.mar.replace('{desde}', '2').replace('{hasta}', String(franja.marHasta))],
                          ['bg-verde', textos.salida],
                        ] as const
                      ).map(([color, texto]) => (
                        <li key={texto} className="flex items-center gap-2">
                          <span aria-hidden="true" className={cn('size-2.5 shrink-0', color)} />
                          {texto}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {incluye.length > 0 && (
                  <ul className="flex flex-col gap-2 texto-cuerpo">
                    {incluye.map((renglon, r) => (
                      <li key={renglon} className={cn('flex items-start gap-2', r >= 3 && 'max-sm:hidden')}>
                        <Check size={18} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" />
                        {renglon}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mt-auto flex flex-col gap-3 pt-2">
                  <div className="flex flex-wrap items-end justify-between gap-4">
                    <p className="tabular-nums">
                      {vista.precio && (
                        <>
                          <span className="block texto-paso font-bold">{vista.precio.monto}</span>
                          <span className="block texto-pequeno">
                            {vista.precio.base}
                            {porGrupo && ` · ${porGrupo}`}
                            {vista.precio.aprox && ` · ${vista.precio.aprox}`}
                          </span>
                        </>
                      )}
                    </p>
                    <span aria-hidden="true" className={cn(botonClases({ variante: 'campana' }), 'group-hover:bg-cafe max-sm:w-full max-sm:justify-center')}>
                      {textosReservar.reservar}
                      <span className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1">→</span>
                    </span>
                  </div>
                  {exclusiones.map((nota) => (
                    <p key={nota} className="texto-pequeno text-tinta-suave">{nota}</p>
                  ))}
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </SectionShell>
  );
}
