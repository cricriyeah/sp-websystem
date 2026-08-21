'use client';

import { WarningCircle, WhatsappLogo } from '@phosphor-icons/react';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

/**
 * Un error que bloquea, con su salida.
 *
 * **No es un toast a proposito.** Un toast se auto-descarta, y un mensaje que
 * explica por que no se pudo cobrar no puede desaparecer solo: el cliente se
 * queda con el problema y sin la explicacion. Esto persiste hasta que la
 * situacion cambie.
 *
 * Lleva el boton de WhatsApp porque es la pieza mas valiosa que tiene este
 * negocio en un momento de fallo y no se estaba usando: del otro lado hay una
 * persona atendiendo. Un canal humano dentro de un mensaje de error convierte
 * una venta perdida en una conversacion; sin el, un corte de red en el wifi de
 * un hotel es una venta que se va sin dejar rastro.
 */
export function ErrorBlock({
  mensaje,
  ayudaTitulo,
  ayudaCta,
  ayudaMensaje,
}: {
  mensaje: string;
  ayudaTitulo: string;
  ayudaCta: string;
  /** Mensaje ya redactado para la vendedora, con fecha, hora y personas. */
  ayudaMensaje: string;
}) {
  return (
    <div
      role="alert"
      className="mt-4 flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3"
    >
      <p className="flex items-start gap-2 text-sm leading-snug text-red-900">
        <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0 text-red-600" />
        {mensaje}
      </p>

      {tieneWhatsapp && (
        <div className="flex flex-col gap-2 border-t border-red-200/70 pt-3">
          <p className="text-xs text-red-900/80">{ayudaTitulo}</p>
          <a
            href={whatsappHref(ayudaMensaje)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 rounded-lg bg-[#25D366] px-4 py-2.5 text-sm font-medium text-white transition-transform active:scale-[0.98]"
          >
            <WhatsappLogo size={18} weight="fill" />
            {ayudaCta}
          </a>
        </div>
      )}
    </div>
  );
}
