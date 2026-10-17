import { CAJA_CAMPO } from '@/components/checkout/estilos';

/**
 * Hueco del formulario de tarjeta mientras llega Stripe: primero el chunk
 * (`next/dynamic`) y despues el iframe (hasta el `onReady` del PaymentElement).
 *
 * Es ESTATICO a proposito: no pulsa ni se anima el contenido de pago. Dibuja las
 * filas del formulario (numero, vencimiento y CVC de 48 px) para que el ojo
 * reconozca la forma que va a aparecer. Sin imports de Stripe: vive en el chunk
 * inicial de las vistas. La altura minima es provisional; se ajusta mirando el
 * salto cuando carga el iframe.
 */
export function EsqueletoPago() {
  return (
    <div aria-hidden="true" className="flex min-h-[19rem] flex-col gap-4">
      <Fila ancho="w-28" />
      <div className="grid grid-cols-2 gap-4">
        <Fila ancho="w-24" />
        <Fila ancho="w-12" />
      </div>
    </div>
  );
}

function Fila({ ancho }: { ancho: string }) {
  return (
    <div className="flex flex-col gap-2">
      <span className={`block h-3 bg-muted/15 ${ancho}`} />
      <span className={`block h-12 ${CAJA_CAMPO}`} />
    </div>
  );
}
