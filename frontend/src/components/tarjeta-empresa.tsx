import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight } from '@phosphor-icons/react/ssr';
import type { MarcaEmpresa } from '@/content/empresas-marca';
import { iniciales } from '@/lib/iniciales';
import { cn } from '@/components/ui/cn';

/** Lo que pinta la tarjeta, proyectado en servidor desde `empresas.ts`. */
export type VistaEmpresa = {
  slug: string;
  nombre: string;
  logo?: string;
  logoLibre?: string;
  campo: MarcaEmpresa['campo'];
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

// Clases completas para que Tailwind las vea.
const CAMPO: Record<VistaEmpresa['campo'], string> = {
  'cafe-claro': 'bg-cafe-claro',
  coral: 'bg-coral',
  verde: 'bg-verde',
  azul: 'bg-azul',
};

const ENLACE = 'inline-flex min-h-11 items-center gap-1 texto-pequeno font-semibold text-cafe';

/**
 * Una empresa del tablero del hub (F10): un bloque 3:2 de color plano con su logo, y debajo quién es,
 * dónde opera, qué hace y a dónde ir. El color es el que deja verse a su logo (ver `MARCAS`).
 *
 * Server Component.
 */
export function TarjetaEmpresa({ empresa, textos }: { empresa: VistaEmpresa; textos: TextosEmpresa }) {
  const externo = (accion: string) => textos.pestanaNueva.replace('{accion}', accion).replace('{empresa}', empresa.nombre);
  const logo = empresa.logoLibre ?? empresa.logo;
  return (
    <li className="group flex flex-col gap-3">
      <div
        className={cn(
          'relative aspect-[3/2] overflow-hidden transition-transform duration-[400ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:-translate-y-1',
          CAMPO[empresa.campo],
        )}
      >
        {logo ? (
          <Image
            src={logo}
            alt={empresa.nombre}
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
            className="object-contain p-[16%] transition-transform duration-[600ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.07]"
          />
        ) : (
          <span aria-hidden="true" className="absolute inset-0 flex items-center justify-center texto-mono-mayus text-5xl font-bold text-tinta">{iniciales(empresa.nombre)}</span>
        )}
      </div>
      <h3 className="mt-2 texto-mono-mayus text-xl font-bold leading-tight text-balance break-words text-foreground">{empresa.nombre}</h3>
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
      <div className="flex flex-wrap gap-x-4">
        {empresa.sedes.map((sede) => (
          <Link key={sede.href} href={sede.href} className={ENLACE}>{textos.verServiciosEn.replace('{sede}', sede.nombre)}</Link>
        ))}
        {empresa.redes.map((red) => (
          <a key={red.url} href={red.url} target="_blank" rel="noopener noreferrer" aria-label={externo(red.nombre)} className={ENLACE}>
            {red.nombre}
            <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        ))}
        {empresa.web && (
          <a href={empresa.web} target="_blank" rel="noopener noreferrer" aria-label={externo(textos.sitioOficial)} className={ENLACE}>
            {textos.sitioOficial}
            <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        )}
      </div>
    </li>
  );
}
