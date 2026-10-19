import type { ComponentType, ReactNode } from 'react';
import type { IconProps } from '@phosphor-icons/react';
import { CalendarCheck, CloudRain, CreditCard, ListChecks } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import { cn } from '@/components/ui/cn';

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
  borde: boolean;
};

function Punto({ Icono, titulo, className, children }: { Icono: ComponentType<IconProps>; titulo: string; className?: string; children: ReactNode }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <Icono size={24} aria-hidden="true" className="text-cafe" />
      <h3 className="texto-subtitulo text-foreground">{titulo}</h3>
      <div className="max-w-[60ch] texto-cuerpo text-tinta-suave">{children}</div>
    </div>
  );
}

/**
 * Pago, clima, cambio de fecha y qué incluye, junto al producto. Una sola política para las
 * cuatro empresas. Sin cajas ni colores de estado: cuatro puntos separados por espacio, para que
 * no se lea como alarma ni como letra chica.
 *
 * Server Component.
 */
export function ReservaTranquila({ id, textos, porcentaje, ejemplo, hrefIncluye, fondo, borde }: Props) {
  return (
    <SectionShell id={id} fondo={fondo} borde={borde} titulo={textos.titulo}>
      <div className="mt-10 grid gap-8 md:grid-cols-2">
        <Punto Icono={CreditCard} titulo={textos.pagoTitulo} className="md:col-span-2">
          <p>{porcentaje === null ? textos.pagoTextoTotal : textos.pagoTexto.replace('{porcentaje}', String(porcentaje))}</p>
          {ejemplo && (
            <div className="mt-4">
              <p className="texto-pequeno text-muted">{textos.ejemploServicio.replace('{servicio}', ejemplo.servicio)}</p>
              <dl className="mt-2 flex flex-wrap gap-x-10 gap-y-3">
                <div>
                  <dt className="texto-pequeno text-muted">{textos.hoyPagas}</dt>
                  <dd className="text-xl font-bold tabular-nums text-foreground">{ejemplo.ahora}</dd>
                </div>
                {ejemplo.resto && (
                  <div>
                    <dt className="texto-pequeno text-muted">{textos.resto}</dt>
                    <dd className="text-xl font-bold tabular-nums text-foreground">{ejemplo.resto}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}
        </Punto>
        <Punto Icono={CloudRain} titulo={textos.climaTitulo}><p>{textos.climaTexto}</p></Punto>
        <Punto Icono={CalendarCheck} titulo={textos.fechaTitulo}><p>{textos.fechaTexto}</p></Punto>
        <Punto Icono={ListChecks} titulo={textos.incluyeTitulo}>
          <p>{textos.incluyeTexto}</p>
          <a href={hrefIncluye} className="mt-2 inline-flex min-h-11 items-center text-cafe">{textos.verIncluye}</a>
        </Punto>
      </div>
    </SectionShell>
  );
}
