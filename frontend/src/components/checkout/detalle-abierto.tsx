'use client';

import { createContext, useContext, useId, useState } from 'react';

/**
 * Qué renglón de "Tu reserva" tiene su detalle abierto. Uno solo a la vez: abrir
 * otro cierra el anterior, así el bloque no crece y no empuja el formulario de
 * tarjeta que está debajo. Sin proveedor, cada renglón lleva su propio estado.
 */
type Contexto = { abierto: string | null; alternar: (id: string) => void };

export const DetalleAbiertoContexto = createContext<Contexto | null>(null);

export function useDetalleAbierto() {
  const id = useId();
  const compartido = useContext(DetalleAbiertoContexto);
  const [local, setLocal] = useState(false);
  if (compartido) {
    return { id, abierto: compartido.abierto === id, alternar: () => compartido.alternar(id) };
  }
  return { id, abierto: local, alternar: () => setLocal((v) => !v) };
}

export function useProveedorDetalle(): Contexto {
  const [abierto, setAbierto] = useState<string | null>(null);
  return { abierto, alternar: (id) => setAbierto((actual) => (actual === id ? null : id)) };
}
