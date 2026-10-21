import { ListaCargos } from '@/components/checkout/pago/renglon-cargo';
import type { ResumenVivo } from '@/components/reserva/contexto-barra';

/**
 * El contenido del resumen del pedido: quién opera (solo el nombre, sin logo), lo elegido en el viaje,
 * las líneas y, en un bloque negro, el total y «pagarás ahora» si difiere. Lo pintan la tarjeta del
 * panel (escritorio y tablet) y la hoja «Ver resumen» (móvil), así no pueden decir cosas distintas.
 */
export function CuerpoResumen({ checkout, lines, lineasViaje = [], sellos = [], total, amountDueNow, cargos = [], notaCargos, estimado = false }: ResumenVivo) {
  return (
    <div className="flex flex-col gap-6">
      {cargos.length > 0 && (
        // Cruza-empresa en pago: cada cobro con su estado, en lugar de solo los nombres.
        <div className="flex flex-col gap-3">
          <ListaCargos cargos={cargos} />
          {notaCargos && <p className="texto-cuerpo">{notaCargos}</p>}
        </div>
      )}
      {cargos.length === 0 && sellos.length > 0 && (
        // Quién opera el viaje: el nombre. En cruza-empresa, uno por empresa.
        <ul className="flex flex-col gap-1">
          {sellos.map((s) => (
            <li key={s.nombre} className="texto-etiqueta text-foreground">{s.nombre}</li>
          ))}
        </ul>
      )}
      {lineasViaje.length > 0 && (
        <dl className="flex flex-col gap-2">
          {lineasViaje.map((linea) => (
            <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4 texto-cuerpo">
              <dt className="font-semibold">{linea.etiqueta}</dt>
              <dd className="text-right first-letter:capitalize">{linea.valor}</dd>
            </div>
          ))}
        </dl>
      )}
      <dl className="flex flex-col gap-3">
        {lines.map((line) => (
          <div key={line.label} className="flex items-center justify-between gap-4 texto-cuerpo">
            <dt>{line.label}</dt>
            <dd className="tabular-nums">{line.amount}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-col gap-3 bg-tinta px-5 py-4 text-hero-ink">
        <div className="flex items-center justify-between gap-4">
          <p className="texto-etiqueta">
            {checkout.total}
            {estimado && <span className="ml-2 font-normal">{checkout.barra.estimado}</span>}
          </p>
          <p className="texto-paso tabular-nums">{total}</p>
        </div>
        {/* Solo cuando difiere del total (anticipo): si no, repetiría la cifra. */}
        {amountDueNow !== total && (
          <div className="flex items-center justify-between gap-4 texto-cuerpo">
            <span>{checkout.amountDueNow}</span>
            <span className="font-semibold tabular-nums">{amountDueNow}</span>
          </div>
        )}
      </div>
    </div>
  );
}
