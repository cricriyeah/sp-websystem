import Image from 'next/image';
import Link from 'next/link';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo } from '@/lib/api';
import { getEmpresa } from '@/content/empresas';
import { colorDeServicio } from '@/lib/color-actividad';
import { vistaDePaquete } from '@/components/vistas-catalogo';
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

type Parte = { nombre: string; empresa: string };

/** Los servicios del paquete en dos mitades: lo que pasa en el mar y lo que pasa en tierra, sin repetir. */
function partesDe(paquete: PaqueteCatalogo): { mar: Parte[]; tierra: Parte[] } {
  const vistos = new Set<number>();
  const partes = { mar: [] as Parte[], tierra: [] as Parte[] };
  for (const componente of [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden)) {
    if (vistos.has(componente.servicio_id)) continue;
    vistos.add(componente.servicio_id);
    const { servicio } = componente;
    const parte = { nombre: servicio.nombre, empresa: getEmpresa(servicio.empresa_slug)?.nombre ?? servicio.empresa_slug };
    partes[colorDeServicio(servicio) === 'mar' ? 'mar' : 'tierra'].push(parte);
  }
  return partes;
}

/**
 * Los paquetes de la sede (F10), cada uno en una tarjeta con foto: qué pasa en el mar y qué pasa en tierra
 * (sale de los servicios del paquete, con su empresa), el precio y el botón «Reservar →». Toda la tarjeta es
 * un solo enlace a la página del paquete. Sin foto propia, el bloque lleva el color de su tipo con su palabra.
 *
 * Server Component.
 */
export function PaquetesSede({ id, lang, moneda, paquetes, textos, textosReservar, fondo }: Props) {
  // El paso de tono: la tarjeta es gris sobre blanco y blanca sobre gris; sus cajas, al revés.
  const tarjeta = fondo === 'cafe-bruma' ? 'bg-superficie' : 'bg-cafe-bruma';
  const caja = fondo === 'cafe-bruma' ? 'bg-cafe-bruma' : 'bg-superficie';

  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
      <div className="mt-10 flex flex-col gap-4">
        {paquetes.map((paquete, i) => {
          const vista = vistaDePaquete(paquete, lang, moneda);
          const { mar, tierra } = partesDe(paquete);
          const incluye = paquete.estrategia_precio === 'por_grupo' ? textos.incluyePersonas.replace('{n}', String(paquete.personas_precio_base)) : null;
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
                {vista.foto ? (
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
              <div className="flex flex-col gap-6 p-6 sm:p-8 lg:p-12">
                <h3 className="texto-paso">{vista.nombre}</h3>
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {([[textos.enElMar, mar], [textos.enTierra, tierra]] as const).map(([titulo, partes]) =>
                    partes.length > 0 && (
                      <div key={titulo} className={cn('p-5', caja)}>
                        <h4 className="texto-subtitulo">{titulo}</h4>
                        <ul className="mt-3 flex flex-col gap-2 texto-cuerpo">
                          {partes.map((parte) => (
                            <li key={parte.nombre}>
                              {parte.nombre}
                              <span className="block texto-cuerpo">{textosReservar.opera.replace('{empresa}', parte.empresa)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ),
                  )}
                </div>
                <div className="mt-auto flex flex-wrap items-center justify-between gap-4">
                  <p className="texto-cuerpo tabular-nums">
                    {vista.precio && (
                      <>
                        <strong className="texto-paso block">{vista.precio.monto}</strong>
                        {vista.precio.base}
                        {incluye && ` · ${incluye}`}
                      </>
                    )}
                  </p>
                  <span aria-hidden="true" className={cn(botonClases({ variante: 'campana' }), 'group-hover:bg-cafe')}>
                    {textosReservar.reservar}
                    <span className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:translate-x-1">→</span>
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </SectionShell>
  );
}
