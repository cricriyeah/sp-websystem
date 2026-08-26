import Image from 'next/image';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type SeasonSectionProps = {
  season: Dictionary['season'];
};

/**
 * La temporada fuerte (el 3er bloque de los 4 que manda el diccionario, jul-sep)
 * es la unica que se distingue: lleva la etiqueta amarilla y su tramo del año va
 * relleno. Coincide siempre con el orden fijo de `season.rows`.
 */
const TEMPORADA_FUERTE = 2;

/**
 * La foto estrella de cada temporada, en el mismo orden que `season.rows`. Vive
 * aqui y no en los diccionarios porque una foto no se traduce: duplicarla en
 * es.json y en.json solo abre la puerta a que las dos versiones se separen.
 *
 * Oct-nov no tiene foto propia de pargo (su especie estrella): usa una toma
 * general de la pesca del dia, que sigue siendo honesta sin prometer un pargo
 * en cuadro.
 */
const FOTOS_TEMPORADA = [
  '/photos/yellowtail-pelicanos-bahia.png',
  '/photos/marlin-en-equipo.png',
  '/photos/cana-doblada-dorado.png',
  '/photos/pesca-del-dia-cubierta.png',
];

/**
 * Calendario de especies: una tira con los 12 meses arriba y cuatro paneles con
 * foto abajo, uno por temporada.
 *
 * **La tira de meses existe para el cliente que ya tiene fecha.** Antes esta
 * seccion eran cuatro columnas de texto gris y quien venia en mayo tenia que
 * leerse los cuatro periodos para saber cual le tocaba. La tira le contesta de
 * un vistazo, sin necesitar doce fotos.
 *
 * **Va en orden de temporada, no de calendario.** Arranca en diciembre porque
 * el primer periodo es dic-mar: en orden Ene→Dic ese bloque quedaria partido en
 * dos, con diciembre huerfano al final de la fila.
 *
 * **Cada temporada tiene cara.** El sistema de color del sitio dice que el color
 * grande lo ponen las fotos (ver globals.css), y esta era la unica seccion que
 * hablaba de peces sin enseñar ninguno.
 *
 * Server Component: es foto y texto, no necesita JavaScript.
 */
export function SeasonSection({ season }: SeasonSectionProps) {
  return (
    <section id="temporadas" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <span aria-hidden className="rev-regla mb-6 block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[58px]">
          {season.headline}
        </h2>
        <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">{season.intro}</p>

        {/* Los tramos se reparten el ancho segun cuantos meses abarcan (`flexGrow`),
            no en cuatro partes iguales: dic-mar son cuatro meses y oct-nov solo
            dos, y pintarlos del mismo largo mentiria sobre el calendario. */}
        <div className="mt-14">
          <p className="text-xs font-semibold text-muted">{season.yearLabel}</p>
          <div className="mt-3 flex gap-1.5">
            {season.rows.map((row, i) => (
              <div key={row.period} style={{ flexGrow: row.months.length }} className="min-w-0">
                <div
                  className={`h-1.5 w-full rounded-full ${
                    i === TEMPORADA_FUERTE ? 'bg-action' : 'bg-accent/30'
                  }`}
                />
                <div className="mt-2 flex">
                  {row.months.map((mes) => (
                    <span
                      key={mes}
                      className="flex-1 text-center text-[10px] whitespace-nowrap text-muted sm:text-xs"
                    >
                      {mes}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
          {season.rows.map((row, i) => (
            <article key={row.period} className="flex flex-col gap-4">
              {/* Apaisada en movil y vertical de `sm` en adelante: apiladas a lo
                  alto, cuatro fotos verticales convierten la seccion en un
                  scroll interminable en telefono. */}
              <div className="relative aspect-[16/10] overflow-hidden sm:aspect-[3/4]">
                <Image
                  src={FOTOS_TEMPORADA[i]}
                  alt={row.star}
                  fill
                  sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                  className="object-cover"
                />
                {/* El texto nunca va directo sobre la foto: siempre sobre un
                    degradado, la misma regla que la portada. */}
                <div
                  aria-hidden
                  className="absolute inset-0"
                  style={{
                    background:
                      'linear-gradient(to top, rgba(10,11,14,0.86) 0%, rgba(10,11,14,0.30) 52%, rgba(10,11,14,0) 100%)',
                  }}
                />

                {i === TEMPORADA_FUERTE && (
                  <span className="absolute top-4 left-4 bg-action px-2.5 py-1 text-[11px] font-semibold text-action-foreground">
                    {season.strongLabel}
                  </span>
                )}

                <div className="absolute inset-x-0 bottom-0 p-5">
                  <p className="text-xs font-semibold text-hero-ink-soft">{row.period}</p>
                  <p className="mt-1 text-2xl leading-tight tracking-tight text-hero-ink">
                    {row.star}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-sm text-foreground">
                  <span className="text-muted">{season.othersLabel}:</span> {row.others}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted">{row.note}</p>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-12 max-w-[60ch] border-t border-border pt-6 text-base leading-relaxed text-foreground">
          {season.note}
        </p>
      </div>
    </section>
  );
}
