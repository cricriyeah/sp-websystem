/**
 * Título fijo de la página de compra, el mismo para pesca, paseo, hospedaje, traslado y paquete
 * («Reserva tu experiencia»): no depende del producto, cuyo nombre a 36 px podía ocupar tres
 * renglones o más. El producto, la sede y las empresas pasan a una línea pequeña debajo.
 */
export function EncabezadoCompra({
  titulo,
  detalle,
}: {
  titulo: string;
  /** Producto · sede · empresa(s) · noches, solo lo que se sepa. */
  detalle?: string;
}) {
  return (
    <header className="mt-4 lg:mt-3">
      <h1 className="texto-pagina text-foreground">{titulo}</h1>
      {detalle && <p className="mt-2 texto-cuerpo text-foreground">{detalle}</p>}
    </header>
  );
}
