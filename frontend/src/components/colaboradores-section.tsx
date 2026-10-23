import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';
import { getEmpresa } from '@/content/empresas';
import { hrefSede } from '@/lib/routes';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { TarjetaEmpresa, type VistaEmpresa } from '@/components/tarjeta-empresa';
import { vistaDeEmpresa } from '@/components/vistas-empresa';

type Textos = Dictionary['hubContenido'];

/**
 * «Empresas locales que nos acompañan», solo en el hub: una fila por empresa, aunque opere en varias
 * sedes. Todo sale de `empresas.ts`; sin descripción no hay fila, sin redes solo el enlace
 * interno y el sitio externo solo si el dueño lo confirmó al día.
 *
 * Server Component.
 */
export function ColaboradoresSection({ sedes, lang, textos, id }: {
  sedes: SedeContenido[]; lang: Locale; textos: Textos; id: string;
}) {
  const filas = new Map<string, VistaEmpresa>();
  for (const sede of sedes) {
    // La protagonista primero y luego las demás.
    const slugs = [...(sede.empresaProtagonistaSlug ? [sede.empresaProtagonistaSlug] : []), ...sede.otrasEmpresas];
    for (const empresa of slugs.map(getEmpresa)) {
      if (!empresa) continue;
      const enlace = { nombre: sede.nombre, href: hrefSede(lang, sede.slug, ANCLA_DE.reservar) };
      const existente = filas.get(empresa.slug);
      if (existente) {
        if (!existente.sedes.some((s) => s.href === enlace.href)) existente.sedes.push(enlace);
        continue;
      }
      filas.set(empresa.slug, vistaDeEmpresa(empresa, lang, [enlace]));
    }
  }
  const visibles = [...filas.values()].filter((fila) => fila.descripcion.trim());
  if (visibles.length === 0) return null;

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-[calc(var(--nav-alto)+16px)] bg-superficie py-16 sm:py-20 lg:py-28">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-12">
        <h2 id={`${id}-titulo`} className="max-w-[24ch] texto-seccion text-foreground">{textos.empresasTitulo}</h2>
        <p className="mt-4 max-w-[60ch] texto-cuerpo text-foreground">{textos.empresasTexto}</p>
        {/* 16 px entre los grupos de una tarjeta (cada una ocupa tres filas en subrejilla) y 48 px entre tarjetas. */}
        <ul className="mt-10 grid gap-x-8 gap-y-4 lg:gap-x-12 sm:grid-cols-2 lg:grid-cols-4 [&>li]:mb-8">
          {visibles.map((empresa) => (
            <TarjetaEmpresa key={empresa.slug} empresa={empresa} textos={textos} />
          ))}
        </ul>
      </div>
    </section>
  );
}
