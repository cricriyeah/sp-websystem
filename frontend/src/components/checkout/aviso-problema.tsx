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
  className?: string;
};

/**
 * El único aviso de problema del checkout: `AvisoAccion` con los textos del diccionario y
 * la salida humana (WhatsApp) siempre a un toque. Reemplaza al antiguo `ErrorBlock`.
 */
export function AvisoProblema({ checkout, feedback, tipo, mensaje, lineasDinero, ayudaMensaje, alAccionar, className }: Props) {
  const textos = mensaje
    ? { ...checkout.problema, [tipo]: { ...checkout.problema[tipo], titulo: mensaje, cuerpo: '' } }
    : checkout.problema;
  const problema = problemaDe(tipo, { lineasDinero, tieneWhatsapp }, textos);
  const ayuda = tieneWhatsapp && tipo !== 'catalogo_caido';

  return (
    <div className={className}>
      <AvisoAccion
        problema={problema}
        alAccionar={(clave) => {
          if (clave === 'whatsapp') window.open(whatsappHref(ayudaMensaje), '_blank', 'noopener');
          else if (alAccionar) alAccionar(clave);
          else if (clave === 'volver') window.history.back();
          else window.location.reload();
        }}
      />
      {ayuda && (
        <a href={whatsappHref(ayudaMensaje)} target="_blank" rel="noopener noreferrer"
          className="mt-2 flex min-h-11 items-center justify-center gap-2 texto-pequeno font-semibold text-tinta-suave hover:text-foreground">
          <WhatsappLogo size={18} weight="fill" aria-hidden />
          {feedback.helpCta}
        </a>
      )}
    </div>
  );
}
