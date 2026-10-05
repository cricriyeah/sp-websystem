/**
 * "Qué compras", siempre arriba y siempre igual: contesta la primera pregunta
 * del cliente antes de pedirle nada. Antes el servicio lo mostraba como un
 * banner dentro de la columna de pasos y el paquete como un `h1` suelto.
 */
export function EncabezadoCompra({
  kicker,
  nombre,
  detalle,
}: {
  kicker: string;
  nombre: string;
  /** Sede · empresa(s) · noches, solo lo que se sepa. */
  detalle?: string;
}) {
  return (
    <header className="mt-6">
      <p className="text-xs font-semibold tracking-wider text-accent uppercase">{kicker}</p>
      <h1 className="mt-1 text-2xl font-bold text-foreground sm:text-3xl">{nombre}</h1>
      {detalle && <p className="mt-1 text-sm text-muted">{detalle}</p>}
    </header>
  );
}
