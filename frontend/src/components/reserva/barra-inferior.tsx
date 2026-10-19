'use client';

import { useEffect, useRef, useState } from 'react';
import { CaretUp } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { CuerpoResumen } from '@/components/checkout/pago/cuerpo-resumen';
import { Button } from '@/components/ui/button';
import { Sheet } from '@/components/ui/sheet';
import { LineaProgreso } from './linea-progreso';
import { useBarra, useRegistroBarra } from './contexto-barra';

type Props = {
  checkout: Dictionary['checkout'];
  actual: number;
  /** Cifra que acompaña al asa (total del pedido, o lo que se paga en este paso). */
  total?: string;
  /** Antes de que el servidor confirme el cobro, la cifra es una estimación y lo dice. */
  estimado: boolean;
};

/**
 * Barra fija de móvil (< 640 px): el asa «Ver resumen · $X», la línea de progreso y el botón único
 * del paso (que `PieDeTarjeta` pinta aquí por portal). Mide su alto y lo publica como `--barra-alto`
 * para que la página, el toast y la ayuda flotante se aparten. Es hermana del contenido que
 * cambia de paso, nunca su hija: un ancestro con `transform` rompería `position: fixed`.
 */
export function BarraInferior({ checkout, actual, total, estimado }: Props) {
  const { setDestino } = useRegistroBarra();
  const { resumen } = useBarra();
  const [hoja, setHoja] = useState(false);
  const barra = useRef<HTMLDivElement>(null);
  const textos = checkout.barra;

  useEffect(() => {
    const elemento = barra.current;
    if (!elemento) return;
    const raiz = document.documentElement;
    const publicar = () => raiz.style.setProperty('--barra-alto', `${elemento.offsetHeight}px`);
    publicar();
    const observador = new ResizeObserver(publicar);
    observador.observe(elemento);
    return () => {
      observador.disconnect();
      raiz.style.setProperty('--barra-alto', '0px');
    };
  }, []);

  return (
    <>
      <div
        ref={barra}
        className="fixed inset-x-0 bottom-0 z-[var(--z-barra)] border-t border-borde bg-blanco pb-[env(safe-area-inset-bottom)] sm:hidden"
      >
        <Button
          variante="libre"
          type="button"
          onClick={() => setHoja(true)}
          aria-haspopup="dialog"
          className="flex min-h-12 w-full items-center justify-between gap-3 px-4 texto-etiqueta text-foreground focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring"
        >
          <span className="tabular-nums">
            {textos.verResumen}
            {total ? ` · ${total}` : ''}
            {estimado && total ? <span className="ml-2 texto-pequeno font-normal text-apagado">{textos.estimado}</span> : null}
          </span>
          <CaretUp size={16} weight="bold" aria-hidden />
        </Button>
        <LineaProgreso
          className="px-4"
          actual={actual}
          nombres={[checkout.stepper.viaje, checkout.stepper.datos, checkout.stepper.pago]}
          plantilla={checkout.stepper.stepOf}
        />
        {/* El botón único del paso llega aquí por portal (PieDeTarjeta). */}
        <div ref={setDestino} className="px-4 pb-3 pt-3 empty:hidden" />
      </div>
      <Sheet abierto={hoja} onCerrar={() => setHoja(false)} titulo={checkout.orderSummaryHeadline} etiquetaCerrar={textos.cerrar} sinBorde>
        {resumen ? <CuerpoResumen {...resumen} /> : null}
      </Sheet>
    </>
  );
}
