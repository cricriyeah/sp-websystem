'use client';

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { StripePanelProps } from '@/components/checkout/pago/tipos';

/** Lo que la hoja «Ver resumen» necesita pintar: el mismo resumen vivo del panel del pedido. */
export type ResumenVivo = Pick<StripePanelProps, 'checkout' | 'lines' | 'lineasViaje' | 'sellos' | 'total' | 'amountDueNow'>;

/** El botón único de la pantalla del asistente móvil, que la barra pinta. */
export type AccionBarra = {
  etiqueta: string;
  /** Estable entre renders: lee la acción vigente de quien la publicó. */
  ejecutar: () => void;
  deshabilitado?: boolean;
  /** Por qué está deshabilitado («Elige una fecha para continuar»); va debajo del botón. */
  razon?: string;
  cargando?: boolean;
  etiquetaCargando?: string;
};

type Valores = {
  /** Sitio de la barra donde se pinta el botón único del paso (null fuera de móvil o sin barra). */
  destino: HTMLElement | null;
  resumen: ResumenVivo | null;
  accion: AccionBarra | null;
};

type Registro = {
  setDestino: (nodo: HTMLElement | null) => void;
  setResumen: (resumen: ResumenVivo) => void;
  setAccion: (accion: AccionBarra | null) => void;
};

const ContextoValores = createContext<Valores>({ destino: null, resumen: null, accion: null });
// Aparte y estable: quien registra (el resumen del panel) no se vuelve a pintar cuando cambia un valor.
const ContextoRegistro = createContext<Registro>({ setDestino: () => {}, setResumen: () => {}, setAccion: () => {} });

/** Une la barra inferior con quien le da el botón (`AsistenteMovil`, o `PieDeTarjeta` por portal) y con quien le da el resumen (`ResumenPedido`). */
export function ProveedorBarra({ children }: { children: ReactNode }) {
  const [destino, setDestino] = useState<HTMLElement | null>(null);
  const [resumen, setResumen] = useState<ResumenVivo | null>(null);
  const [accion, setAccion] = useState<AccionBarra | null>(null);
  const registro = useMemo<Registro>(() => ({ setDestino, setResumen, setAccion }), []);
  const valores = useMemo(() => ({ destino, resumen, accion }), [destino, resumen, accion]);
  return (
    <ContextoRegistro.Provider value={registro}>
      <ContextoValores.Provider value={valores}>{children}</ContextoValores.Provider>
    </ContextoRegistro.Provider>
  );
}

export const useBarra = () => useContext(ContextoValores);
export const useRegistroBarra = () => useContext(ContextoRegistro);

/** El resumen del panel del pedido se publica para la hoja; solo si cambió su contenido. */
export function useRegistrarResumen(resumen: ResumenVivo) {
  const { setResumen } = useRegistroBarra();
  const ultimo = useRef('');
  const { checkout, ...datos } = resumen;
  const huella = JSON.stringify(datos);
  useEffect(() => {
    if (huella === ultimo.current) return;
    ultimo.current = huella;
    setResumen({ checkout, ...JSON.parse(huella) });
  }, [huella, checkout, setResumen]);
}
