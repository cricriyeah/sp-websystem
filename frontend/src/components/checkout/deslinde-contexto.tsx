'use client';

import { createContext, useContext } from 'react';

/** Las empresas que operan lo que se compra: el deslinde de responsabilidad que se enlaza es el de ellas. */
export const DeslindeEmpresas = createContext<readonly string[]>([]);

export function useDeslindeEmpresas(): readonly string[] {
  return useContext(DeslindeEmpresas);
}
