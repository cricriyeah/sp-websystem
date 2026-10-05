'use client';

import { useCallback, useState } from 'react';
import {
  ayudaInicial, descartarAyuda, motivoDeAyuda, ofreceAyudaFlotante, registrarTropiezo,
  type TipoTropiezo,
} from '@/lib/ayuda-contextual';

/** Estado de React sobre las reglas puras de `lib/ayuda-contextual.ts`. */
export function useAyudaContextual() {
  const [estado, setEstado] = useState(ayudaInicial);
  const tropezar = useCallback(
    (tipo: TipoTropiezo) => setEstado((actual) => registrarTropiezo(actual, tipo)),
    [],
  );
  const descartar = useCallback(() => setEstado((actual) => descartarAyuda(actual)), []);
  return {
    visible: ofreceAyudaFlotante(estado),
    motivo: motivoDeAyuda(estado),
    tropezar,
    descartar,
  };
}
