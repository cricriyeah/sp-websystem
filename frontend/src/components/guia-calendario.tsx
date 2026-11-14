import type { CSSProperties } from 'react';
import type { FilaCalendario, TemaGuia } from '@/content/guias';
import { cn } from '@/components/ui/cn';
import { MarcaMesActual } from '@/components/guia-mes-actual';

type Props = {
  filas: FilaCalendario[];
  /** `es-MX` / `en-US`: de ahí salen la inicial y el nombre de cada mes. */
  idioma: string;
  /** El color de las casillas en temporada: el del tema de la guía. */
  tema: TemaGuia;
  textos: { enTemporada: string; temporadaFuerte: string; datoDeZona: string; ahora: string; resumenFila: string; resumenFuerte: string };
};

const MESES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

// Clases completas para que Tailwind las vea. El coral lleva su tono hondo: el blanco sobre el coral vivo no alcanza 4,5:1.
const CASILLA: Record<TemaGuia, string> = { mar: 'bg-azul', traslado: 'bg-coral-hondo', estancia: 'bg-verde' };

/** El nombre de cada mes en el idioma de la página (`formato` corto para la casilla, largo para quien lo oye). */
function nombresDeMes(idioma: string, formato: 'narrow' | 'long'): string[] {
  const formateador = new Intl.DateTimeFormat(idioma, { month: formato, timeZone: 'UTC' });
  return MESES.map((mes) => formateador.format(new Date(Date.UTC(2026, mes - 1, 1))));
}

/**
 * El calendario de una guía: una tira de doce casillas por especie, sobre fondo arena. La casilla de color es un mes en
 * temporada y la más alta, un mes fuerte: la diferencia va en la forma y no solo en el color. Arriba, una marca dice
 * en qué mes estamos (`MarcaMesActual`, isla cliente). En el teléfono el nombre va sobre su tira y las doce casillas caben a lo ancho, sin deslizar.
 *
 * Las casillas crecen una tras otra al entrar en pantalla (`.casilla-crece`, quietas con «reducir movimiento»).
 * Quien usa lector de pantalla no recorre 84 casillas: cada fila se lee como una frase («Orcas: enero, febrero…»).
 *
 * Server Component.
 */
export function GuiaCalendario({ filas, idioma, tema, textos }: Props) {
  const iniciales = nombresDeMes(idioma, 'narrow');
  const nombres = nombresDeMes(idioma, 'long');
  const hayFuertes = filas.some((fila) => (fila.fuertes?.length ?? 0) > 0);
  const enOrden = (meses: number[]) => MESES.filter((mes) => meses.includes(mes)).map((mes) => nombres[mes - 1]).join(', ');
  const REJILLA = 'grid gap-2 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-8';
  const TIRA = 'grid grid-cols-12 gap-0.5 sm:gap-1';

  return (
    <div className="mt-10">
      {/* La marca del mes de hoy, sobre su columna. */}
      <div aria-hidden="true" className={REJILLA}>
        <span className="hidden lg:block" />
        <MarcaMesActual etiqueta={textos.ahora} className={cn(TIRA, 'mb-2 min-h-7')} />
      </div>

      <ul className="flex flex-col gap-6 lg:gap-4">
        {filas.map((fila) => (
          <li key={fila.nombre} className={cn(REJILLA, 'lg:items-end')}>
            <p aria-hidden="true" className="text-lg font-semibold leading-snug lg:pb-1.5">
              {fila.nombre}
              {fila.fuente === 'region' && <span className="block texto-pequeno font-normal">{textos.datoDeZona}</span>}
            </p>
            <p className="sr-only">
              {textos.resumenFila.replace('{nombre}', fila.nombre).replace('{meses}', enOrden(fila.meses))}
              {fila.fuertes?.length ? ` ${textos.resumenFuerte.replace('{meses}', enOrden(fila.fuertes))}` : ''}
            </p>
            <div aria-hidden="true" className={cn(TIRA, 'h-14 items-end')}>
              {MESES.map((mes) => {
                const enTemporada = fila.meses.includes(mes);
                const fuerte = Boolean(fila.fuertes?.includes(mes));
                return (
                  <span
                    key={mes}
                    style={{ '--mes': mes - 1 } as CSSProperties}
                    className={cn(
                      'casilla-crece flex items-end justify-center pb-1.5 texto-mono-mayus text-sm font-bold leading-none',
                      fuerte ? 'h-14' : 'h-10',
                      enTemporada ? cn(CASILLA[tema], 'text-white') : 'bg-superficie text-foreground',
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
          <span aria-hidden="true" className={cn('block h-5 w-4', CASILLA[tema])} />
          {textos.enTemporada}
        </li>
        {hayFuertes && (
          <li className="flex items-end gap-2.5">
            <span aria-hidden="true" className={cn('block h-7 w-4', CASILLA[tema])} />
            {textos.temporadaFuerte}
          </li>
        )}
      </ul>
    </div>
  );
}
