import Image from 'next/image';
import type { SedeTemporadas } from '@/content/sedes-tipos';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type SeasonSectionProps = {
  id: string;
  titulo: string;
  /** El calendario sale del cuerpo de la sede, con la foto de cada temporada. */
  temporadas: SedeTemporadas;
  fondo: Fondo;
  borde: boolean;
};

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
export function SeasonSection({ id, titulo, temporadas, fondo, borde }: SeasonSectionProps) {
  return (
    <SectionShell id={id} fondo={fondo} borde={borde} titulo={titulo}>
      <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">{temporadas.intro}</p>

      {/* Los tramos se reparten el ancho segun cuantos meses abarcan (`flexGrow`),
          no en cuatro partes iguales: dic-mar son cuatro meses y oct-nov solo
          dos, y pintarlos del mismo largo mentiria sobre el calendario. */}
      <div className="mt-14">
        <p className="text-sm font-semibold text-muted">{temporadas.etiquetaCalendario}</p>
        <div className="mt-3 flex gap-1.5">
          {temporadas.filas.map((fila) => (
            <div key={fila.periodo} style={{ flexGrow: fila.meses.length }} className="min-w-0">
              <div
                className={`h-1.5 w-full rounded-full ${
                  fila.fuerte ? 'bg-action' : 'bg-accent/30'
                }`}
              />
              <div className="mt-2 flex">
                {fila.meses.map((mes) => (
                  <span
                    key={mes}
                    className="flex-1 text-center texto-pie whitespace-nowrap text-muted"
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
        {temporadas.filas.map((fila) => (
          <article key={fila.periodo} className="flex flex-col gap-4">
            {/* Apaisada en movil y vertical de `sm` en adelante: apiladas a lo
                alto, cuatro fotos verticales convierten la seccion en un
                scroll interminable en telefono. */}
            <div className="relative aspect-[16/10] overflow-hidden sm:aspect-[3/4]">
              <Image
                src={fila.foto}
                alt={fila.estrella}
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
                    'var(--scrim-temporada)',
                }}
              />

              {fila.fuerte && (
                <span className="absolute top-4 left-4 bg-action px-2.5 py-1 texto-pie font-semibold text-action-foreground">
                  {temporadas.etiquetaFuerte}
                </span>
              )}

              <div className="absolute inset-x-0 bottom-0 p-5">
                <p className="text-sm font-semibold text-hero-ink-soft">{fila.periodo}</p>
                <p className="mt-1 text-2xl leading-tight tracking-tight text-hero-ink">
                  {fila.estrella}
                </p>
              </div>
            </div>

            <div>
              <p className="text-sm text-foreground">
                <span className="text-muted">{temporadas.etiquetaOtras}:</span> {fila.otras}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted">{fila.nota}</p>
            </div>
          </article>
        ))}
      </div>

      <p className="mt-12 max-w-[60ch] border-t border-border pt-6 text-base leading-relaxed text-foreground">
        {temporadas.nota}
      </p>
    </SectionShell>
  );
}
