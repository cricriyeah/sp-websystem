import type { ReactNode } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CifraContada } from '@/components/ui/cifra-contada';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type Textos = Dictionary['sedeContenido']['tranquilidad'];

/** El ejemplo de pago, calculado en la página con el servicio destacado. */
export type EjemploPago = { servicio: string; ahora: string; resto: string | null };

type Props = {
  id: string;
  textos: Textos;
  /** El `porcentaje_anticipo` de un servicio de la sede que lo permite; `null` = todos se pagan completos. */
  porcentaje: number | null;
  ejemplo: EjemploPago | null;
  hrefIncluye: string;
  fondo: Fondo;
};

function Cifra({ cifra, titulo, children }: { cifra: string; titulo: string; children: ReactNode }) {
  return (
    <li className="flex flex-col gap-3">
      <CifraContada cifra={cifra} className="texto-grande block text-cafe-claro tabular-nums" />
      <h3 className="texto-subtitulo">{titulo}</h3>
      <div className="max-w-[34ch] texto-cuerpo">{children}</div>
    </li>
  );
}

/**
 * Pago, clima y cambio de fecha como tres cifras grandes en la banda negra (F10), que cuentan desde cero
 * al entrar. Una sola política para las cuatro empresas. Debajo, el enlace a «qué incluye» cada servicio.
 *
 * Server Component (las cifras que cuentan son una isla cliente).
 */
export function ReservaTranquila({ id, textos, porcentaje, ejemplo, hrefIncluye, fondo }: Props) {
  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
      <ul className="mt-12 grid gap-12 md:grid-cols-3 md:gap-8 lg:mt-16">
        <Cifra cifra={porcentaje === null ? textos.cifraTotal : `${porcentaje} %`} titulo={textos.pagoTitulo}>
          <p>{porcentaje === null ? textos.pagoTextoTotal : textos.pagoTexto.replace('{porcentaje}', String(porcentaje))}</p>
          {ejemplo && (
            <div className="mt-4">
              <p>{textos.ejemploServicio.replace('{servicio}', ejemplo.servicio)}</p>
              <dl className="mt-2 flex flex-wrap gap-x-8 gap-y-2">
                <div>
                  <dt>{textos.hoyPagas}</dt>
                  <dd className="text-xl font-bold tabular-nums">{ejemplo.ahora}</dd>
                </div>
                {ejemplo.resto && (
                  <div>
                    <dt>{textos.resto}</dt>
                    <dd className="text-xl font-bold tabular-nums">{ejemplo.resto}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}
        </Cifra>
        <Cifra cifra={textos.cifraFecha} titulo={textos.fechaTitulo}>
          <p>{textos.fechaTexto}</p>
        </Cifra>
        <Cifra cifra={textos.cifraTotal} titulo={textos.climaTitulo}>
          <p>{textos.climaTexto}</p>
        </Cifra>
      </ul>
      <p className="mt-12 flex flex-wrap items-center gap-x-4 texto-cuerpo">
        {textos.incluyeTexto}
        <a href={hrefIncluye} className="inline-flex min-h-11 items-center font-semibold text-cafe-claro">{textos.verIncluye}</a>
      </p>
    </SectionShell>
  );
}
