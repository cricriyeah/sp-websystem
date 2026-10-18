import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CabeceraMinima } from '@/components/reserva/cabecera-minima';
import { WaitNotice } from '@/components/wait-notice';
import type { FasePedido } from './use-pago-pedido';

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug: string;
  fase: FasePedido;
  confirmandoLargo: boolean;
};

/** Espera del paquete: reanudando, capturando los pagos o confirmando con el servidor. */
export function PantallaEspera({ lang, dict, sedeSlug, fase, confirmandoLargo }: Props) {
  const { checkout, feedback, pedido: textos, nav } = dict;
  return (
    <div className="min-h-dvh bg-background">
      <CabeceraMinima lang={lang} nav={nav} volverHref={`/${lang}/sede/${sedeSlug}`} volverLabel={checkout.back} marcaFija />
      <div className="mx-auto max-w-2xl px-6 pt-[calc(4rem_+_var(--nav-alto))] pb-20 text-center sm:px-8">
        <WaitNotice
          mensaje={fase === 'resumiendo'
            ? textos.resuming
            : fase === 'confirmando'
              ? (confirmandoLargo ? checkout.siguiendoConfirmando : checkout.confirmandoTitulo)
              : feedback.payingWait}
          mensajeLento={fase === 'resumiendo' || fase === 'confirmando' ? undefined : feedback.paySlow}
        />
      </div>
    </div>
  );
}
