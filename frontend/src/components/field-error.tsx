'use client';

import { useEffect, useState } from 'react';
import { WarningCircle } from '@phosphor-icons/react';
import { useReducedMotion } from 'motion/react';
import { Despliegue } from '@/components/checkout/despliegue';

/**
 * El error, pegado al campo que lo causo.
 *
 * Un aviso que solo dice "hay un error" obliga al cliente a sostener eso en la
 * cabeza y ademas ponerse a buscar donde: una tarea de busqueda montada encima
 * de una tarea de formulario. El mensaje va aqui, debajo de su campo.
 *
 * **Icono y texto, no solo color.** Cerca del 8% de los hombres tiene algun
 * grado de daltonismo y para ellos un borde rojo sin nada mas no existe. La
 * redundancia no es adorno: es lo que hace que el mensaje llegue por mas de un
 * canal.
 */
export function FieldError({ id, mensaje }: { id: string; mensaje: string }) {
  return (
    <p id={id} role="alert" className="mt-1.5 flex items-start gap-1.5 text-xs text-red-600">
      <WarningCircle size={14} weight="fill" className="mt-px shrink-0" />
      <span className="leading-snug">{mensaje}</span>
    </p>
  );
}

/**
 * `FieldError` que entra y sale animado, para usar siempre montado:
 * `<ErrorDeCampo id=… mensaje={error} />` con `mensaje` vacío = sin error.
 *
 * - Aparecer de golpe empuja todo lo de abajo; el despliegue lo hace gradual.
 * - Conserva el último texto mientras se pliega (el estado ya lo vació).
 * - Si al aparecer queda fuera de pantalla (el cliente confirmó un paso desde
 *   más abajo), lo trae a la vista y lleva el foco al campo que lo causó. Si ya
 *   se ve, no mueve nada: un error de un campo que se acaba de dejar no debe
 *   arrancar al cliente de donde está.
 */
export function ErrorDeCampo({ id, mensaje, className }: { id: string; mensaje?: string | null; className?: string }) {
  const [ultimo, setUltimo] = useState('');
  if (mensaje && mensaje !== ultimo) setUltimo(mensaje);
  const hay = Boolean(mensaje);
  const sinMovimiento = useReducedMotion();

  useEffect(() => {
    if (!hay) return;
    const el = document.getElementById(id);
    if (!el) return;
    const caja = el.getBoundingClientRect();
    if (caja.top >= 0 && caja.bottom <= window.innerHeight) return;
    el.scrollIntoView({ block: 'center', behavior: sinMovimiento ? 'auto' : 'smooth' });
    document.querySelector<HTMLElement>(`[aria-describedby~="${id}"]`)?.focus({ preventScroll: true });
  }, [hay, id, sinMovimiento]);

  return (
    <Despliegue abierto={hay} className={className}>
      <FieldError id={id} mensaje={ultimo} />
    </Despliegue>
  );
}

/**
 * Clases del campo cuando trae error. Se aplican junto a las propias del input
 * para que el borde rojo sea el mismo en todos lados.
 */
export const CLASES_CAMPO_CON_ERROR = 'border-red-400 focus:border-red-500 focus:ring-red-200';

/**
 * Props de accesibilidad del input con error. `aria-invalid` es lo que hace que
 * un lector de pantalla lo anuncie como invalido, y `aria-describedby` lo une
 * con el texto de abajo — sin eso, el mensaje existe visualmente pero no para
 * quien no lo ve.
 */
export function propsDeError(idError: string, hayError: boolean) {
  return hayError
    ? ({ 'aria-invalid': true, 'aria-describedby': idError } as const)
    : ({} as const);
}
