import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowUpRight,
  FacebookLogo,
  Globe,
  InstagramLogo,
  TiktokLogo,
  YoutubeLogo,
} from '@phosphor-icons/react/ssr';
import type { Icon } from '@phosphor-icons/react';
import { iniciales } from '@/lib/iniciales';
import { cn } from '@/components/ui/cn';

/** Lo que pinta la tarjeta, proyectado en servidor desde `empresas.ts`. */
export type VistaEmpresa = {
  slug: string;
  nombre: string;
  logo?: string;
  sedes: { nombre: string; href: string }[];
  tambienConocidaComo?: string;
  descripcion: string;
  redes: { nombre: string; url: string }[];
  /** Solo si el dueño confirmó que el sitio está al día. */
  web?: string;
  contacto?: { tipo: 'whatsapp' | 'telefono'; numero: string };
};

export type TextosEmpresa = {
  verServiciosEn: string;
  sitioOficial: string;
  pestanaNueva: string;
  tambienConocida: string;
  telefono: string;
  whatsapp: string;
};

const ENLACE = 'inline-flex min-h-11 items-center gap-1 texto-pequeno font-semibold text-cafe';
const CIRCULO = 'inline-flex size-11 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde';

/** El icono de cada red; una que no conocemos cae en la flecha de enlace externo. */
const ICONO_DE_RED: { patron: RegExp; icono: Icon }[] = [
  { patron: /instagram/i, icono: InstagramLogo },
  { patron: /facebook/i, icono: FacebookLogo },
  { patron: /tiktok/i, icono: TiktokLogo },
  { patron: /youtube/i, icono: YoutubeLogo },
];

/**
 * Una empresa local (hub y detalles de F10): su logo suelto sobre fondo blanco, y debajo quién es, dónde
 * opera, qué hace y a dónde ir: sus servicios en el sitio, sus redes (con el icono de cada una) y su página
 * web (con un globo). Con una o dos empresas (los detalles) va `horizontal`: el logo a la izquierda y
 * el texto a su lado.
 *
 * Server Component.
 */
export function TarjetaEmpresa({ empresa, textos, horizontal = false }: { empresa: VistaEmpresa; textos: TextosEmpresa; horizontal?: boolean }) {
  const externo = (accion: string) => textos.pestanaNueva.replace('{accion}', accion).replace('{empresa}', empresa.nombre);
  return (
    <li className={cn('group', horizontal ? 'grid gap-6 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] md:items-center md:gap-x-14' : 'flex flex-col gap-4')}>
      <div className={cn('relative flex h-28 items-center', horizontal && 'md:h-40')}>
        {empresa.logo ? (
          <Image
            src={empresa.logo}
            alt={empresa.nombre}
            width={320}
            height={160}
            sizes="(min-width: 1024px) 20vw, 50vw"
            className="h-full w-auto max-w-full object-contain object-left transition-transform duration-[600ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.04]"
          />
        ) : (
          <span aria-hidden="true" className="texto-mono-mayus text-5xl font-bold text-tinta">{iniciales(empresa.nombre)}</span>
        )}
      </div>
      <div className="flex flex-col gap-3">
        <h3 className="texto-mono-mayus text-xl font-bold leading-tight text-balance break-words text-foreground">{empresa.nombre}</h3>
        <p className="texto-pequeno font-semibold text-foreground">{empresa.sedes.map((s) => s.nombre).join(' · ')}</p>
        {empresa.tambienConocidaComo && (
          <p className="texto-pequeno text-foreground">{textos.tambienConocida.replace('{nombre}', empresa.tambienConocidaComo)}</p>
        )}
        <p className="max-w-[60ch] texto-cuerpo text-foreground">{empresa.descripcion}</p>
        {empresa.contacto && (
          <p className="texto-pequeno text-foreground">
            {empresa.contacto.tipo === 'whatsapp' ? textos.whatsapp : textos.telefono}:{' '}
            <a href={`tel:${empresa.contacto.numero.replace(/[^\d+]/g, '')}`} className="inline-flex min-h-11 items-center font-semibold">
              {empresa.contacto.numero}
            </a>
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {empresa.sedes.map((sede) => (
            <Link key={sede.href} href={sede.href} className={ENLACE}>{textos.verServiciosEn.replace('{sede}', sede.nombre)}</Link>
          ))}
        </div>
        {(empresa.redes.length > 0 || empresa.web) && (
          <div className="flex flex-wrap gap-2">
            {empresa.redes.map((red) => {
              const Icono = ICONO_DE_RED.find((r) => r.patron.test(red.nombre))?.icono ?? ArrowUpRight;
              return (
                <a key={red.url} href={red.url} target="_blank" rel="noopener noreferrer" aria-label={externo(red.nombre)} className={CIRCULO}>
                  <Icono size={22} aria-hidden="true" />
                </a>
              );
            })}
            {empresa.web && (
              <a href={empresa.web} target="_blank" rel="noopener noreferrer" aria-label={externo(textos.sitioOficial)} className={CIRCULO}>
                <Globe size={22} aria-hidden="true" />
              </a>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
