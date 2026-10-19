import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight } from '@phosphor-icons/react/ssr';
import { EmpresaSello } from '@/components/ui/empresa-sello';

/** Lo que pinta la fila, proyectado en servidor desde `empresas.ts`. */
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
  foto: { src: string; alt: string } | null;
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

/**
 * Una empresa del directorio del hub: quién es, dónde opera, qué hace y a dónde ir. Filas y no
 * tarjetas: una sede con una sola empresa dejaría una tarjeta huérfana en la rejilla.
 *
 * Server Component.
 */
export function FilaEmpresa({ empresa, textos }: { empresa: VistaEmpresa; textos: TextosEmpresa }) {
  const externo = (accion: string) => textos.pestanaNueva.replace('{accion}', accion).replace('{empresa}', empresa.nombre);
  return (
    <li className="grid gap-4 py-6 md:grid-cols-2 md:gap-8 xl:grid-cols-12">
      <div className="flex flex-col gap-3 xl:col-span-4">
        <EmpresaSello nombre={empresa.nombre} logo={empresa.logo} tamano={64} />
        <h3 className="font-display text-2xl font-bold text-balance break-words text-foreground">{empresa.nombre}</h3>
        <p className="texto-pequeno text-muted">{empresa.sedes.map((s) => s.nombre).join(' · ')}</p>
        {empresa.tambienConocidaComo && (
          <p className="texto-pequeno text-muted">{textos.tambienConocida.replace('{nombre}', empresa.tambienConocidaComo)}</p>
        )}
      </div>
      <div className="flex flex-col gap-3 xl:col-span-8 lg:flex-row lg:gap-8">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <p className="max-w-[60ch] texto-cuerpo text-foreground">{empresa.descripcion}</p>
          {empresa.contacto && (
            <p className="texto-pequeno text-tinta-suave">
              {empresa.contacto.tipo === 'whatsapp' ? textos.whatsapp : textos.telefono}:{' '}
              <a href={`tel:${empresa.contacto.numero.replace(/[^\d+]/g, '')}`} className="inline-flex min-h-11 items-center font-semibold text-foreground">
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
        </div>
        {empresa.foto && (
          <div className="relative hidden aspect-[16/10] w-64 shrink-0 overflow-hidden rounded-card lg:block">
            <Image src={empresa.foto.src} alt={empresa.foto.alt} fill sizes="256px" className="object-cover" />
          </div>
        )}
      </div>
    </li>
  );
}
