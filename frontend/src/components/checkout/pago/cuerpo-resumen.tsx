import { EmpresaSello } from '@/components/ui/empresa-sello';
import { ListaCargos } from '@/components/checkout/pago/renglon-cargo';
import type { ResumenVivo } from '@/components/reserva/contexto-barra';

/**
 * El contenido del resumen del pedido: sello de quien opera, lo elegido en el viaje, las líneas,
 * el total y «pagarás ahora» si difiere. Lo pintan la tarjeta del panel (escritorio y tablet) y la
 * hoja «Ver resumen» (móvil), así no pueden decir cosas distintas.
 */
export function CuerpoResumen({ checkout, lines, lineasViaje = [], sellos = [], total, amountDueNow, cargos = [], notaCargos }: ResumenVivo) {
  return (
    <>
      {cargos.length > 0 && (
        // Cruza-empresa en pago: cada cobro con su estado, en lugar de solo los sellos.
        <div className="mb-4 flex flex-col gap-3 border-b border-border pb-4">
          <ListaCargos cargos={cargos} />
          {notaCargos && <p className="texto-pequeno text-apagado">{notaCargos}</p>}
        </div>
      )}
      {cargos.length === 0 && sellos.length > 0 && (
        // Quién opera el viaje, sin caja dentro de la caja: sello y nombre. En cruza-empresa, uno por empresa.
        <ul className="mb-4 flex flex-col gap-3 border-b border-border pb-4">
          {sellos.map((s) => (
            <li key={s.nombre}>
              <EmpresaSello nombre={s.nombre} logo={s.logo} tamano={32} mostrarNombre />
            </li>
          ))}
        </ul>
      )}
      {lineasViaje.length > 0 && (
        <dl className="mb-4 flex flex-col gap-2 border-b border-border pb-4">
          {lineasViaje.map((linea) => (
            <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-muted">{linea.etiqueta}</dt>
              <dd className="text-right text-foreground first-letter:capitalize">{linea.valor}</dd>
            </div>
          ))}
        </dl>
      )}
      <dl className="flex flex-col gap-3">
        {lines.map((line) => (
          <div key={line.label} className="flex items-center justify-between text-sm">
            <dt className="text-muted">{line.label}</dt>
            <dd className="text-foreground">{line.amount}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-5 flex items-center justify-between border-t border-border pt-5">
        <p className="text-sm font-medium text-foreground">{checkout.total}</p>
        <p className="text-lg font-medium tracking-tight text-foreground">{total}</p>
      </div>

      {/* Solo cuando difiere del total (anticipo): si no, repetiría la cifra. */}
      {amountDueNow !== total && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="text-muted">{checkout.amountDueNow}</span>
          <span className="text-foreground">{amountDueNow}</span>
        </div>
      )}
    </>
  );
}
