import type { FilaCalendario } from '@/content/guias';
import { cn } from '@/components/ui/cn';

type Props = {
  filas: FilaCalendario[];
  /** `es-MX` / `en-US`: de ahí salen la inicial y el nombre de cada mes. */
  idioma: string;
  textos: { enTemporada: string; temporadaFuerte: string; datoDeZona: string; resumenFila: string; resumenFuerte: string };
};

const MESES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

/** El nombre de cada mes en el idioma de la página (`formato` corto para la casilla, largo para quien lo oye). */
function nombresDeMes(idioma: string, formato: 'narrow' | 'long'): string[] {
  const formateador = new Intl.DateTimeFormat(idioma, { month: formato, timeZone: 'UTC' });
  return MESES.map((mes) => formateador.format(new Date(Date.UTC(2026, mes - 1, 1))));
}

/**
 * El calendario de una guía: una tira de doce casillas por especie, sobre fondo blanco. La casilla en tinta es un mes en temporada y la
 * más alta, un mes fuerte: la diferencia va en la forma y no solo en el color. En el teléfono el nombre va sobre su
 * tira y las doce casillas caben a lo ancho, sin deslizar de lado.
 *
 * Quien usa lector de pantalla no recorre 84 casillas: cada fila se lee como una frase («Orcas: enero, febrero…»).
 *
 * Server Component.
 */
export function GuiaCalendario({ filas, idioma, textos }: Props) {
  const iniciales = nombresDeMes(idioma, 'narrow');
  const nombres = nombresDeMes(idioma, 'long');
  const hayFuertes = filas.some((fila) => (fila.fuertes?.length ?? 0) > 0);
  const enOrden = (meses: number[]) => MESES.filter((mes) => meses.includes(mes)).map((mes) => nombres[mes - 1]).join(', ');

  return (
    <div className="mt-10">
      <ul className="flex flex-col gap-6 lg:gap-4">
        {filas.map((fila) => (
          <li key={fila.nombre} className="grid gap-2 lg:grid-cols-[18rem_minmax(0,1fr)] lg:items-end lg:gap-8">
            <p aria-hidden="true" className="text-lg font-semibold leading-snug lg:pb-1.5">
              {fila.nombre}
              {fila.fuente === 'region' && <span className="block texto-pequeno font-normal">{textos.datoDeZona}</span>}
            </p>
            <p className="sr-only">
              {textos.resumenFila.replace('{nombre}', fila.nombre).replace('{meses}', enOrden(fila.meses))}
              {fila.fuertes?.length ? ` ${textos.resumenFuerte.replace('{meses}', enOrden(fila.fuertes))}` : ''}
            </p>
            <div aria-hidden="true" className="grid h-12 grid-cols-12 items-end gap-0.5 sm:gap-1">
              {MESES.map((mes) => {
                const enTemporada = fila.meses.includes(mes);
                const fuerte = Boolean(fila.fuertes?.includes(mes));
                return (
                  <span
                    key={mes}
                    className={cn(
                      'flex items-end justify-center pb-1.5 texto-mono-mayus text-sm font-bold leading-none',
                      fuerte ? 'h-12' : 'h-9',
                      enTemporada ? 'bg-tinta text-white' : 'bg-cafe-bruma text-foreground',
                    )}
                  >
                    {iniciales[mes - 1]}
                  </span>
                );
              })}
            </div>
          </li>
        ))}
      </ul>

      <ul className="mt-8 flex flex-wrap items-end gap-x-8 gap-y-3 texto-cuerpo">
        <li className="flex items-end gap-2.5">
          <span aria-hidden="true" className="block h-5 w-4 bg-tinta" />
          {textos.enTemporada}
        </li>
        {hayFuertes && (
          <li className="flex items-end gap-2.5">
            <span aria-hidden="true" className="block h-7 w-4 bg-tinta" />
            {textos.temporadaFuerte}
          </li>
        )}
      </ul>
    </div>
  );
}
