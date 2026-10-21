import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

/** Una reseña ya confirmada por su empresa: el filtro se hace en el servidor, antes de las props. */
export type OpinionVista = {
  autor: string;
  texto: string;
  idioma: 'es' | 'en';
  fuente: { nombre: string; url: string };
  empresa: { nombre: string; logo?: string };
};

type Props = {
  id: string;
  lang: Locale;
  opiniones: OpinionVista[];
  textos: Dictionary['sedeContenido']['opiniones'];
  fondo: Fondo;
};

const MAX = 3;

/**
 * Opiniones atribuidas a la empresa que las publicó, nunca como si las verificara Sun Baja
 * Experience: sin estrellas ni carrusel, cada cita con su empresa y su fuente, en su idioma
 * original (sin traducir). La primera va grande; las demás, en 2 columnas desde 768 px.
 *
 * Server Component.
 */
export function OpinionesEmpresas({ id, lang, opiniones, textos, fondo }: Props) {
  const citas = opiniones.slice(0, MAX);
  if (citas.length === 0) return null;

  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
      <div className={cn('mt-10 grid gap-10', citas.length > 1 && 'md:grid-cols-2')}>
        {citas.map((cita, i) => (
          <figure key={`${cita.autor}-${cita.fuente.url}`} className={cn('flex flex-col gap-4', i === 0 && citas.length > 1 && 'md:col-span-2')}>
            <blockquote lang={cita.idioma} className={cn('line-clamp-3', i === 0 ? 'texto-subtitulo' : 'texto-cuerpo')}>
              <p>“{cita.texto}”</p>
            </blockquote>
            <figcaption className="flex flex-col gap-1 texto-pequeno">
              <span className="font-semibold text-foreground">{cita.autor}</span>
              <span className="flex items-center gap-2">
                <span aria-hidden="true" className="inline-flex">
                  <EmpresaSello nombre={cita.empresa.nombre} logo={cita.empresa.logo} tamano={24} />
                </span>
                {textos.publicadaPor.replace('{empresa}', cita.empresa.nombre)}
              </span>
              {cita.idioma !== lang && <span>{cita.idioma === 'es' ? textos.originalEs : textos.originalEn}</span>}
              <a href={cita.fuente.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center font-semibold text-cafe">
                {textos.verEn.replace('{fuente}', cita.fuente.nombre)}
              </a>
            </figcaption>
          </figure>
        ))}
      </div>
    </SectionShell>
  );
}
