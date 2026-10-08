'use client';

import { useId, useState } from 'react';
import { Question } from '@phosphor-icons/react';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import type { Dictionary } from '@/app/[lang]/dictionaries';

/**
 * "¿Por qué más de un pago?", en línea y a pedido. Un pedido con varias empresas
 * se cobra una vez por empresa; si el cliente no lo esperaba, el segundo
 * formulario de tarjeta se lee como un error. La explicación se queda a la vista
 * hasta que él la cierra (un aviso que se va solo se pierde justo cuando se
 * quiere leer), la alcanza el teclado y la anuncia el lector de pantalla.
 */
export function PorQueVariosPagos({ dict }: { dict: Dictionary }) {
  const [abierto, setAbierto] = useState(false);
  const id = useId();

  return (
    <div>
      <AccionTexto
        tono="acento"
        icono={<Question size={14} weight="bold" aria-hidden />}
        abierto={abierto}
        aria-controls={id}
        onClick={() => setAbierto((v) => !v)}
      >
        {dict.pedido.whyManyPayments}
      </AccionTexto>
      <div
        id={id}
        className={`grid transition-[grid-template-rows,opacity,visibility] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none ${
          abierto ? 'visible grid-rows-[1fr] opacity-100' : 'invisible grid-rows-[0fr] opacity-0'
        }`}
      >
        <p className="min-h-0 max-w-prose overflow-hidden text-xs leading-relaxed text-muted">
          {dict.pedido.whyManyPaymentsBody}
        </p>
      </div>
    </div>
  );
}
