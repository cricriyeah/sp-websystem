'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { cancelarOrdenPublica, type ResumenOrden } from '@/lib/api';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { textoDeSituacion } from '@/lib/pendientes-texto';

type Opciones = {
  dict: Dictionary;
  /** Hay una orden cruza-empresa creada, con o sin dinero retenido. */
  activo: boolean;
  sedeSlug: string;
  ordenId: number | null;
  checkoutId: string;
  producto: string;
  /** Se liberó lo retenido: el checkout vuelve al formulario con lo ya capturado. */
  onLiberada: (linea: string) => void;
};

/**
 * Cancelar la orden cruza-empresa desde el checkout. Con la orden creada, la flecha y el Atrás
 * del navegador no salen en silencio: abren un `AlertDialog`. Antes de confirmar el texto solo dice
 * que se cancela y que el resultado se muestra aquí (no promete inmediatez); después, el texto
 * sale de `situacion`, igual que en `continuar-reservacion`.
 */
export function useCancelarOrden({ dict, activo, sedeSlug, ordenId, checkoutId, producto, onLiberada }: Opciones) {
  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [resultado, setResultado] = useState<ResumenOrden | null>(null);
  const [problema, setProblema] = useState<'errorServidor' | 'sinConexion' | null>(null);
  const textos = dict.pedido.cancelarOrden;

  // Atrás del navegador: una entrada de más con la misma URL (y el estado de Next) que se repone
  // cada vez que se consume, así Atrás abre el diálogo en lugar de dejar la orden a medias.
  useEffect(() => {
    if (!activo) return;
    window.history.pushState(window.history.state, '', window.location.href);
    const alVolver = () => {
      window.history.pushState(window.history.state, '', window.location.href);
      setConfirmando(true);
    };
    window.addEventListener('popstate', alVolver);
    return () => window.removeEventListener('popstate', alVolver);
  }, [activo]);

  const cancelar = async () => {
    if (cancelando || ordenId === null) return;
    setCancelando(true);
    try {
      const respuesta = await cancelarOrdenPublica(sedeSlug, ordenId, checkoutId);
      setProblema(null);
      if (respuesta.situacion === 'cancelada_liberada') onLiberada(textoDeSituacion(dict.continuar, respuesta).linea1);
      else setResultado(respuesta);
    } catch (error) {
      const detalle = error && typeof error === 'object' && 'detail' in error ? error.detail : null;
      if (detalle && typeof detalle === 'object' && 'situacion' in detalle && 'montos' in detalle) {
        setResultado(detalle as ResumenOrden);
      } else {
        setProblema(navigator.onLine ? 'errorServidor' : 'sinConexion');
      }
    } finally {
      setCancelando(false);
      setConfirmando(false);
    }
  };

  const abrir = useCallback(() => setConfirmando(true), []);

  const dialogo = (
    <AlertDialog
      abierto={confirmando}
      titulo={textos.titulo}
      cuerpo={textos.cuerpo}
      etiquetaSegura={textos.seguir}
      etiquetaDestructiva={textos.cancelar}
      onSegura={() => setConfirmando(false)}
      onDestructiva={() => { void cancelar(); }}
    />
  );

  // El resultado que no se resuelve volviendo al formulario (devolución, error): queda a la vista.
  const linea = resultado
    ? textoDeSituacion(dict.continuar, resultado).linea1
    : problema ? dict.continuar[problema].replace('{producto}', producto) : null;
  const whatsapp = resultado && tieneWhatsapp
    ? whatsappHref(dict.continuar.whatsappFolio.replace('{folio}', String(resultado.folio)).replace('{producto}', resultado.producto))
    : null;
  const aviso = linea ? (
    <div role="status" aria-live="polite" className="mx-auto mb-2 max-w-6xl px-6 sm:px-8 lg:px-12">
      <div className="flex flex-col gap-2 rounded-card border border-borde bg-blanco p-4">
        <p className="texto-cuerpo text-foreground">{linea}</p>
        {whatsapp && (
          <a href={whatsapp} target="_blank" rel="noopener noreferrer" className="texto-etiqueta text-foreground underline">
            {textos.escribir}
          </a>
        )}
      </div>
    </div>
  ) : null;

  return {
    abrir,
    dialogo,
    aviso,
    /** La orden ya no se puede pagar: no se muestra el formulario de tarjeta. */
    cerrada: resultado !== null,
  };
}
