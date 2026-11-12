import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { Star } from '@phosphor-icons/react/ssr';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { CLASE_FONDO, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

/** Una reseña ya confirmada por su empresa: el filtro se hace en el servidor, antes de las props. */
export type OpinionVista = {
  autor: string;
  texto: string;
  idioma: 'es' | 'en';
  /** La calificación que dio ese cliente (1 a 5), si la fuente la tiene. Nunca un promedio. */
  estrellas?: number;
  fuente: { nombre: string; url: string };
  empresa: { nombre: string; logo?: string };
};

type Props = {
  id: string;
  lang: Locale;
  opiniones: OpinionVista[];
  textos: Dictionary['sedeContenido']['opiniones'];
  /** Las flechas del carril, las mismas de las demás filas que se arrastran. */
  textosFila: { anterior: string; siguiente: string };
  fondo: Fondo;
  /** El perfil donde están todas (Google de la marca): un solo enlace bajo el carril en lugar de uno por tarjeta. */
  todas?: { nombre: string; url: string };
};

// La tarjeta da un paso de tono contra la banda: blanca sobre arena y arena sobre blanco (como las de paquetes).
const TARJETA: Record<Fondo, string> = {
  blanco: 'bg-cafe-bruma text-foreground',
  'cafe-bruma': 'bg-superficie text-foreground',
  tinta: 'bg-superficie text-foreground',
};

/**
 * Opiniones como tarjetas en el carril que se arrastra (el mismo de «Tu día de pesca»): cada una con la cita arriba y
 * quién la escribió abajo, todas a la misma altura. Atribuidas a quien las publicó, nunca como si las verificara
 * Sun Baja Experience: cada una con las estrellas que dio ese cliente (nunca un promedio), en su idioma original.
 *
 * Server Component (el carril es una isla cliente).
 */
export function OpinionesEmpresas({ id, lang, opiniones, textos, textosFila, fondo, todas }: Props) {
  if (opiniones.length === 0) return null;

  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={cn('scroll-mt-[calc(var(--nav-alto)+16px)] py-16 sm:py-20 lg:py-28', CLASE_FONDO[fondo])}>
      <FilaArrastrable
        cabeza={<h2 id={`${id}-titulo`} className="rev max-w-[24ch] texto-seccion">{textos.titulo}</h2>}
        etiqueta={textos.titulo}
        textos={textosFila}
      >
        {opiniones.map((cita) => (
          <figure
            key={`${cita.autor}-${cita.texto.slice(0, 24)}`}
            className={cn(
              'rev m-0 flex min-h-[20rem] flex-[0_0_82vw] snap-start flex-col justify-between gap-8 p-6 sm:flex-[0_0_clamp(18rem,30vw,26rem)] sm:p-8',
              TARJETA[fondo],
            )}
          >
            <div className="flex flex-col gap-4">
            {cita.estrellas ? (
              // Las estrellas de ESTE cliente, como las dio en la fuente: llenas las que puso, vacías las que no.
              <span role="img" aria-label={textos.estrellas.replace('{n}', String(cita.estrellas))} className="flex gap-1 text-cafe">
                {[1, 2, 3, 4, 5].map((n) => (
                  <Star key={n} size={22} weight={n <= cita.estrellas! ? 'fill' : 'regular'} aria-hidden="true" />
                ))}
              </span>
            ) : null}
            <blockquote lang={cita.idioma} className="text-xl leading-snug">
              <p className="line-clamp-[8]">“{cita.texto}”</p>
            </blockquote>
            </div>
            <figcaption className="flex flex-col gap-1">
              <span className="texto-mono-mayus text-lg font-bold leading-tight">{cita.autor}</span>
              <span className="flex items-center gap-2 texto-pequeno">
                {cita.empresa.logo && (
                  <span aria-hidden="true" className="inline-flex">
                    <EmpresaSello nombre={cita.empresa.nombre} logo={cita.empresa.logo} tamano={24} />
                  </span>
                )}
                {cita.empresa.logo ? textos.publicadaPor.replace('{empresa}', cita.empresa.nombre) : textos.resenaEn.replace('{fuente}', cita.fuente.nombre)}
                {cita.idioma !== lang && <> · {cita.idioma === 'es' ? textos.originalEs : textos.originalEn}</>}
              </span>
              {cita.fuente.url !== todas?.url && (
                <a href={cita.fuente.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center self-start font-semibold text-cafe">
                  {textos.verEn.replace('{fuente}', cita.fuente.nombre)}
                </a>
              )}
            </figcaption>
          </figure>
        ))}
      </FilaArrastrable>
      {todas && (
        <div className="mx-auto mt-8 max-w-[1440px] px-pagina">
          <a href={todas.url} target="_blank" rel="noopener noreferrer" className="rev inline-flex min-h-11 items-center gap-2 font-semibold text-cafe">
            {textos.verTodas.replace('{fuente}', todas.nombre)}
            <span aria-hidden="true">→</span>
          </a>
        </div>
      )}
    </section>
  );
}
