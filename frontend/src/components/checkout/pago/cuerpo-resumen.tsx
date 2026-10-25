import { CifraViva } from '@/components/ui/cifra-viva';
import { Despliegue } from '@/components/ui/despliegue';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { ListaCargos } from '@/components/checkout/pago/renglon-cargo';
import type { ResumenVivo } from '@/components/reserva/contexto-barra';

/**
 * El contenido del resumen del pedido: quién opera (su logo y su nombre), lo elegido en el viaje,
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
        // Quién opera el viaje: su logo con el nombre. En cruza-empresa, uno por empresa.
        <ul className="flex flex-col gap-3">
          {sellos.map((s) => (
            <li key={s.nombre}>
              <EmpresaSello nombre={s.nombre} logo={s.logo} tamano={32} mostrarNombre />
            </li>
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

      <div className="flex flex-col bg-tinta px-5 py-4 text-hero-ink">
        <div className="flex items-center justify-between gap-4">
          <p className="texto-etiqueta">
            {checkout.total}
            {estimado && <span className="ml-2 font-normal">{checkout.barra.estimado}</span>}
          </p>
          <p className="texto-paso tabular-nums"><CifraViva valor={total} /></p>
        </div>
        {/* Solo cuando difiere del total (anticipo): si no, repetiría la cifra. Se despliega hacia abajo; el
            espacio de arriba va dentro de la fila para que crezca con ella. */}
        <Despliegue abierto={amountDueNow !== total}>
          <div className="flex items-center justify-between gap-4 pt-3 texto-cuerpo">
            <span>{checkout.amountDueNow}</span>
            <span className="font-semibold tabular-nums"><CifraViva valor={amountDueNow} /></span>
          </div>
        </Despliegue>
      </div>
    </div>
  );
}
