'use client';

import { WhatsappLogo } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { AvisoAccion } from '@/components/ui/aviso-accion';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { problemaDe, type ClaveAccion, type TipoProblema } from '@/lib/problema-reserva';

type Props = {
  checkout: Dictionary['checkout'];
  feedback: Dictionary['feedback'];
  tipo: TipoProblema;
  /** Texto exacto del servidor o del banco: pasa a ser el «qué ocurrió» y reemplaza el cuerpo del tipo. */
  mensaje?: string;
  lineasDinero?: string[];
  /** Mensaje ya redactado para la vendedora (fecha, hora y personas). */
  ayudaMensaje: string;
  /** Cómo se resuelve cada acción en esta vista; sin él, «reintentar» recarga y «volver» regresa. */
  alAccionar?: (clave: ClaveAccion) => void;
  /** Conserva el cuerpo del tipo («No se hizo ningún cobro.») aunque `mensaje` reemplace el título. */
  conservarCuerpo?: boolean;
  /** El enlace de WhatsApp. Por defecto siempre; la tarjeta rechazada lo ofrece desde el tercer fallo. */
  ofrecerAyuda?: boolean;
  className?: string;
};

/**
 * El único aviso de problema del checkout: `AvisoAccion` con los textos del diccionario y
 * la salida humana (WhatsApp) siempre a un toque. Reemplaza al antiguo `ErrorBlock`.
 */
export function AvisoProblema({
  checkout, feedback, tipo, mensaje, lineasDinero, ayudaMensaje, alAccionar, conservarCuerpo = false, ofrecerAyuda = true, className,
}: Props) {
  const textos = mensaje
    ? {
      ...checkout.problema,
      [tipo]: { ...checkout.problema[tipo], titulo: mensaje, cuerpo: conservarCuerpo ? checkout.problema[tipo].cuerpo : '' },
    }
    : checkout.problema;
  const problema = problemaDe(tipo, { lineasDinero, tieneWhatsapp }, textos);
  const ayuda = tieneWhatsapp && tipo !== 'catalogo_caido' && ofrecerAyuda;

  // Un error es el bloque de coral: la ayuda va dentro, en blanco. Un aviso es la caja suave: la ayuda debajo.
  const enCampo = problema.tono === 'error';
  const enlaceAyuda = ayuda ? (
    <a href={whatsappHref(ayudaMensaje)} target="_blank" rel="noopener noreferrer"
      className={enCampo
        ? 'flex min-h-11 items-center gap-2 texto-pequeno font-semibold text-hero-ink underline underline-offset-4'
        : 'mt-2 flex min-h-11 items-center justify-center gap-2 texto-pequeno font-semibold text-tinta-suave hover:text-foreground'}>
      <WhatsappLogo size={18} weight="fill" aria-hidden />
      {feedback.helpCta}
    </a>
  ) : null;

  return (
    <div className={className}>
      <AvisoAccion
        problema={problema}
        etiquetaDinero={tipo === 'tarjeta_rechazada' ? checkout.etiquetaDinero : undefined}
        pie={enCampo ? enlaceAyuda : undefined}
        alAccionar={(clave) => {
          if (clave === 'whatsapp') window.open(whatsappHref(ayudaMensaje), '_blank', 'noopener');
          else if (alAccionar) alAccionar(clave);
          else if (clave === 'volver') window.history.back();
          else window.location.reload();
        }}
      />
      {!enCampo && enlaceAyuda}
    </div>
  );
}
