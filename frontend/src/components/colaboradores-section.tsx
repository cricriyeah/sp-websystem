import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';
import { hrefSede } from '@/lib/routes';

/** One brand per company, even when it collaborates with several destinations. */
export function ColaboradoresSection({ sedes, lang, copy, id = 'colaboradores' }: {
  sedes: SedeContenido[]; lang: Locale; copy: Dictionary['hub']; id?: string;
}) {
  const marcas = new Map<string, { nombre: string; logo: string | null; web?: string; redes?: { nombre: string; url: string }[]; sedes: SedeContenido[] }>();
  for (const sede of sedes) {
    const empresas = [
      ...(sede.empresaFundadoraSlug && sede.empresaFundadoraNombre ? [{ slug: sede.empresaFundadoraSlug, nombre: sede.empresaFundadoraNombre, logo: sede.logo, enlaceExterno: sede.web, redes: sede.redes }] : []),
      ...sede.otrasEmpresas,
    ];
    for (const empresa of empresas) {
      const existente = marcas.get(empresa.slug);
      if (existente) {
        if (!existente.sedes.some(s => s.slug === sede.slug)) existente.sedes.push(sede);
      } else marcas.set(empresa.slug, { nombre: empresa.nombre, logo: empresa.logo ?? null, web: empresa.enlaceExterno, redes: empresa.redes, sedes: [sede] });
    }
  }
  if (marcas.size === 0) return null;
  return (
    <section id={id} className="scroll-mt-28 border-t border-border bg-surface py-16">
      <div className="mx-auto max-w-[1440px] px-6 sm:px-8 lg:px-12">
        <h2 className="text-4xl text-foreground sm:text-5xl">{copy.partnersTitle}</h2>
        <p className="mt-4 max-w-2xl text-muted">{copy.partnersIntro}</p>
        <div className="mt-10 grid gap-x-12 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
          {[...marcas].map(([slug, marca]) => (
            <article key={slug} className="flex flex-col items-start gap-4 border-t border-border py-6">
              {marca.logo ? <Image src={marca.logo} alt={marca.nombre} width={210} height={90} className="h-20 w-52 object-contain object-left" /> : <h3 className="flex min-h-20 items-center text-2xl text-foreground">{marca.nombre}</h3>}
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {marca.sedes.map(sede => <Link key={sede.slug} href={hrefSede(lang, sede.slug)} className="text-sm text-muted underline underline-offset-4 hover:text-accent">{sede.nombre}</Link>)}
              </div>
              <div className="flex flex-wrap gap-4 text-sm text-accent">
                {marca.web && <a href={marca.web} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-4">{copy.websiteLabel}<ArrowUpRight size={14} /></a>}
                {marca.redes?.map(red => <a key={red.url} href={red.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-4">{red.nombre}<ArrowUpRight size={14} /></a>)}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
