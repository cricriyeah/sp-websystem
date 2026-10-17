/**
 * "Qué compras", siempre arriba y siempre igual: contesta la primera pregunta
 * del cliente antes de pedirle nada. Antes el servicio lo mostraba como un
 * banner dentro de la columna de pasos y el paquete como un `h1` suelto.
 */
export function EncabezadoCompra({
  nombre,
  detalle,
}: {
  nombre: string;
  /** Sede · empresa(s) · noches, solo lo que se sepa. */
  detalle?: string;
}) {
  return (
    <header className="mt-4 lg:mt-3">
      <h1 className="texto-pagina text-foreground">{nombre}</h1>
      {detalle && <p className="mt-2 text-sm text-muted">{detalle}</p>}
    </header>
  );
}
