import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import type { PaqueteCatalogo } from '@/lib/api';
import { fechaDeComponente } from '@/lib/calendario-paquete';
import type { ComponentePedido } from '@/lib/pedido-payload';

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug: string;
  paquete: PaqueteCatalogo;
  /** Fecha de inicio elegida (o la mínima si no hubo): de ella salen las fechas de cada servicio. */
  inicio: string;
  componentes: Record<string, ComponentePedido>;
  formatearFecha: (iso: string) => string;
};

/** Pantalla de éxito del paquete (una empresa y cruza-empresa): lista lo comprado. */
export function PantallaExito({ lang, dict, sedeSlug, paquete, inicio, componentes, formatearFecha }: Props) {
  const { checkout, pedido: textos, nav, footer } = dict;
  return (
    <div className="min-h-dvh bg-background">
      <CabeceraMinima lang={lang} nav={nav} volverHref={`/${lang}/sede/${sedeSlug}`} volverLabel={checkout.back} />
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
        <h1 className="texto-seccion text-foreground">{textos.success.title}</h1>
        <p className="text-sm text-muted">{textos.success.body}</p>
        <div className="w-full border border-border bg-card p-5 text-left">
          <p className="mb-3 texto-pequeno font-semibold text-muted">
            {textos.success.componentsHeadline}
          </p>
          <ul className="flex flex-col gap-2">
            {paquete.servicios_asociados.map((item) => (
              <li key={item.id} className="flex flex-wrap justify-between gap-2 text-sm text-foreground">
                <span>{item.servicio.nombre}</span>
                <span className="text-muted">
                  {formatearFecha(fechaDeComponente(inicio, item.dia_estancia))}
                  {' · '}{componentes[item.servicio.slug]?.personas ?? item.personas_incluidas}{' '}
                  {(componentes[item.servicio.slug]?.personas ?? item.personas_incluidas) === 1
                    ? checkout.peopleUnit.one : checkout.peopleUnit.other}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <CheckoutFooter lang={lang} footer={footer} nav={nav} />
    </div>
  );
}
