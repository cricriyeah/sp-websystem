import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowUpRight,
  FacebookLogo,
  Globe,
  InstagramLogo,
  TiktokLogo,
  WhatsappLogo,
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

// El camino a reservar manda: texto de cuerpo con flecha. Las redes, que sacan del sitio, van después y calladas.
const ENLACE = 'group/enlace inline-flex min-h-11 items-center gap-2 texto-cuerpo font-semibold text-cafe';
const CIRCULO = 'inline-flex size-11 items-center justify-center rounded-full bg-cafe-bruma text-foreground transition-colors hover:bg-borde';

/** El icono de cada red; una que no conocemos cae en la flecha de enlace externo. */
const ICONO_DE_RED: { patron: RegExp; icono: Icon }[] = [
  { patron: /instagram/i, icono: InstagramLogo },
  { patron: /facebook/i, icono: FacebookLogo },
  { patron: /tiktok/i, icono: TiktokLogo },
  { patron: /youtube/i, icono: YoutubeLogo },
];

/**
 * Una empresa local (hub y detalles de F10), en tres grupos: quién es (logo, nombre y, si difiere, el nombre
 * de su sitio), qué hace (la descripción) y qué puedes hacer (ver sus servicios en cada sede, y después sus
 * redes, WhatsApp y sitio web como círculos). En el hub cada tarjeta es una subrejilla de tres filas: los
 * tres grupos quedan a la misma altura en toda la fila aunque las descripciones midan distinto. Con una o
 * dos empresas (los detalles) va `horizontal`: el logo a la izquierda y el texto a su lado.
 *
 * Server Component.
 */
export function TarjetaEmpresa({ empresa, textos, horizontal = false }: { empresa: VistaEmpresa; textos: TextosEmpresa; horizontal?: boolean }) {
  const externo = (accion: string) => textos.pestanaNueva.replace('{accion}', accion).replace('{empresa}', empresa.nombre);
  const digitos = empresa.contacto?.numero.replace(/\D/g, '') ?? '';
  const logo = (
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
  );
  const nombre = (
    <div className="flex flex-col gap-1">
      <h3 className="texto-mono-mayus text-xl font-bold leading-tight text-balance break-words text-foreground">{empresa.nombre}</h3>
      {empresa.tambienConocidaComo && (
        <p className="texto-pequeno text-foreground">{textos.tambienConocida.replace('{nombre}', empresa.tambienConocidaComo)}</p>
      )}
    </div>
  );
  const descripcion = <p className="max-w-[60ch] texto-cuerpo text-foreground">{empresa.descripcion}</p>;
  const hayCirculos = empresa.redes.length > 0 || Boolean(empresa.web) || empresa.contacto?.tipo === 'whatsapp';
  const acciones = (
    <div className="flex flex-col items-start gap-3">
      <div className="flex flex-col items-start">
        {empresa.sedes.map((sede) => (
          <Link key={sede.href} href={sede.href} className={ENLACE}>
            {textos.verServiciosEn.replace('{sede}', sede.nombre)}
            <span aria-hidden="true" className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover/enlace:translate-x-1">→</span>
          </Link>
        ))}
      </div>
      {empresa.contacto?.tipo === 'telefono' && (
        <p className="texto-pequeno text-foreground">
          {textos.telefono}:{' '}
          <a href={`tel:+${digitos}`} className="inline-flex min-h-11 items-center font-semibold">{empresa.contacto.numero}</a>
        </p>
      )}
      {hayCirculos && (
        <div className="flex flex-wrap gap-2">
          {empresa.contacto?.tipo === 'whatsapp' && (
            <a href={`https://wa.me/${digitos}`} target="_blank" rel="noopener noreferrer" aria-label={externo(`${textos.whatsapp} ${empresa.contacto.numero}`)} className={CIRCULO}>
              <WhatsappLogo size={20} aria-hidden="true" />
            </a>
          )}
          {empresa.redes.map((red) => {
            const Icono = ICONO_DE_RED.find((r) => r.patron.test(red.nombre))?.icono ?? ArrowUpRight;
            return (
              <a key={red.url} href={red.url} target="_blank" rel="noopener noreferrer" aria-label={externo(red.nombre)} className={CIRCULO}>
                <Icono size={20} aria-hidden="true" />
              </a>
            );
          })}
          {empresa.web && (
            <a href={empresa.web} target="_blank" rel="noopener noreferrer" aria-label={externo(textos.sitioOficial)} className={CIRCULO}>
              <Globe size={20} aria-hidden="true" />
            </a>
          )}
        </div>
      )}
    </div>
  );

  if (horizontal) {
    return (
      <li className="group grid gap-6 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] md:items-center md:gap-x-14">
        {logo}
        <div className="flex flex-col gap-4">{nombre}{descripcion}{acciones}</div>
      </li>
    );
  }
  // Tres filas de la rejilla del padre (`colaboradores-section`): quién es · qué hace · qué puedes hacer.
  return (
    <li className="group row-span-3 grid grid-rows-subgrid gap-y-4">
      <div className="flex flex-col gap-4">{logo}{nombre}</div>
      {descripcion}
      {acciones}
    </li>
  );
}
