'use client';

import { useCallback } from 'react';
import type { PasoId } from '@/lib/pasos-checkout';

type Destino = { paso: PasoId; campo: string };

function buscarControl(campo: string): HTMLElement | null {
  const directo = document.getElementById(campo);
  // Un campo de contacto se nombra por el id de su error: el control lo referencia con aria-describedby.
  const porError = document.querySelector<HTMLElement>(`[aria-describedby~="${campo}"]`);
  const control = directo?.matches('input,select,textarea,button') ? directo : porError ?? directo;
  return control && control.getClientRects().length > 0 ? control : null;
}

/** Espera a que el paso monte (abrir una tarjeta anima su contenido) y enfoca el control. */
function enfocarCuandoMonte(campo: string, intentos = 20): void {
  const control = campo ? buscarControl(campo) : null;
  if (control) {
    control.focus({ preventScroll: true });
    control.scrollIntoView({ block: 'center', behavior: 'smooth' });
    return;
  }
  if (intentos > 0) {
    window.setTimeout(() => enfocarCuandoMonte(campo, intentos - 1), 50);
    return;
  }
  // Sin control enfocable (una fecha): al menos se trae a la vista la tarjeta del paso.
  document.querySelector<HTMLElement>('[data-tarjeta-foco]')?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

/**
 * «Corregir»: abre el paso al que pertenece el problema y enfoca el campo después de que
 * monte. Un paso anterior se reabre; el actual se deja abierto; Pago no abre nada.
 * En el asistente móvil, `irAPantalla` lleva a la pantalla del campo en lugar de reabrir tarjetas.
 */
export function useCorregir(
  actual: PasoId,
  setEditando: (paso: PasoId | null) => void,
  irAPantalla?: (destino: Destino) => void,
) {
  return useCallback((destino: Destino) => {
    if (irAPantalla) irAPantalla(destino);
    else if (destino.paso !== 'pago') setEditando(destino.paso === actual ? null : destino.paso);
    enfocarCuandoMonte(destino.campo);
  }, [actual, setEditando, irAPantalla]);
}
