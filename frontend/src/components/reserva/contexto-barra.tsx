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

/** Lo que publica quien tiene el botón: la acción tal cual, sin la función estable. */
export type AccionPublicable = Omit<AccionBarra, 'ejecutar'> & { alPulsar: () => void };

type Valores = {
  resumen: ResumenVivo | null;
  /** El botón de la pantalla (`AsistenteMovil`): «Continuar», o un pago que todavía carga. */
  accion: AccionBarra | null;
  /**
   * El botón que aporta el contenido de la pantalla y que manda sobre el de la pantalla: «Cómo
   * pagas» (crea el pago) y el formulario de Stripe (cobra; vive dentro de `<Elements>`).
   */
  accionContenido: AccionBarra | null;
};

type Registro = {
  setResumen: (resumen: ResumenVivo) => void;
  setAccion: (accion: AccionBarra | null) => void;
  setAccionContenido: (accion: AccionBarra | null) => void;
};

const ContextoValores = createContext<Valores>({ resumen: null, accion: null, accionContenido: null });
// Aparte y estable: quien registra (el resumen del panel) no se vuelve a pintar cuando cambia un valor.
const ContextoRegistro = createContext<Registro>({ setResumen: () => {}, setAccion: () => {}, setAccionContenido: () => {} });

/** Une la barra inferior con quien le da el botón y con quien le da el resumen (`ResumenPedido`). */
export function ProveedorBarra({ children }: { children: ReactNode }) {
  const [resumen, setResumen] = useState<ResumenVivo | null>(null);
  const [accion, setAccion] = useState<AccionBarra | null>(null);
  const [accionContenido, setAccionContenido] = useState<AccionBarra | null>(null);
  const registro = useMemo<Registro>(() => ({ setResumen, setAccion, setAccionContenido }), []);
  const valores = useMemo(() => ({ resumen, accion, accionContenido }), [resumen, accion, accionContenido]);
  return (
    <ContextoRegistro.Provider value={registro}>
      <ContextoValores.Provider value={valores}>{children}</ContextoValores.Provider>
    </ContextoRegistro.Provider>
  );
}

export const useBarra = () => useContext(ContextoValores);
export const useRegistroBarra = () => useContext(ContextoRegistro);

/**
 * Publica el botón en la barra mientras el componente está montado (`null` lo retira). La barra
 * recibe una función estable que lee la acción vigente: publicar un objeto nuevo en cada render
 * la volvería a pintar sin fin.
 */
export function usePublicarAccion(accion: AccionPublicable | null, sitio: 'pantalla' | 'contenido') {
  const registro = useRegistroBarra();
  const publicar = sitio === 'pantalla' ? registro.setAccion : registro.setAccionContenido;
  const alPulsar = useRef(accion?.alPulsar);
  useEffect(() => { alPulsar.current = accion?.alPulsar; });
  const { etiqueta, deshabilitado, razon, cargando, etiquetaCargando } = accion ?? {};
  useEffect(() => {
    publicar(etiqueta === undefined ? null : {
      etiqueta, deshabilitado, razon, cargando, etiquetaCargando, ejecutar: () => alPulsar.current?.(),
    });
  }, [publicar, etiqueta, deshabilitado, razon, cargando, etiquetaCargando]);
  useEffect(() => () => publicar(null), [publicar]);
}

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
