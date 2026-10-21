'use client';

import { useEffect, useState } from 'react';
import { WarningCircle } from '@phosphor-icons/react';
import { useReducedMotion } from 'framer-motion';
import { Despliegue } from './despliegue';

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
    <p id={id} role="alert" className="mt-1.5 flex items-start gap-1.5 text-sm text-error">
      <WarningCircle size={14} weight="fill" className="mt-px shrink-0" />
      <span className="leading-snug">{mensaje}</span>
    </p>
  );
}

/**
 * Si el error `id` acaba de aparecer y queda fuera de pantalla (el cliente confirmó un paso desde
 * más abajo), lo trae a la vista y lleva el foco al campo que lo causó (el que lo cita con
 * `aria-describedby`). Si ya se ve, no mueve nada. Lo usan `ErrorDeCampo` y `Field`.
 */
export function useLlevarAlError(id: string, hay: boolean) {
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
  useLlevarAlError(id, hay);

  return (
    <Despliegue abierto={hay} className={className}>
      <FieldError id={id} mensaje={ultimo} />
    </Despliegue>
  );
}

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
