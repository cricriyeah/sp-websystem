import { MarcaEmpresaCompra, type EmpresaDeCompra } from '@/components/checkout/marca-empresa-compra';

/**
 * Título fijo de la página de compra, el mismo para pesca, paseo, hospedaje, traslado y paquete
 * («Reserva tu experiencia»): no depende del producto, cuyo nombre a 36 px podía ocupar tres
 * renglones o más. El producto, la sede y las empresas pasan a una línea pequeña debajo.
 *
 * Checkout de una sola empresa: su logo abre esa línea (PFD, 2026-11-17). La barra ya no lleva el logo de la empresa
 * (junto al regreso se leía «DESTINOS × SAL Y SOL»), así que aquí, donde el cliente mira al empezar la compra, se sigue
 * viendo a quién le paga. Es el logo largo a 48 px si lo tiene (ya trae el nombre dibujado: no se repite en el texto);
 * si no, el sello de 48 px y el nombre en la línea.
 */
export function EncabezadoCompra({
  titulo,
  detalle,
  empresa,
}: {
  titulo: string;
  /** Producto · sede · empresa(s) · noches, solo lo que se sepa. */
  detalle?: string;
  /** La empresa que cobra, solo si es una (con varias, el aviso de cargos ya nombra a cada una). */
  empresa?: EmpresaDeCompra;
}) {
  // El nombre va en el texto solo si el logo no lo trae y el detalle no lo dice ya (el paquete lo nombra).
  const nombreEnTexto = empresa && !empresa.logoLargo && !detalle?.includes(empresa.nombre);
  const linea = nombreEnTexto ? [detalle, empresa.nombre].filter(Boolean).join(' · ') : detalle;
  return (
    <header className="mt-4 lg:mt-3">
      <h1 className="texto-pagina text-foreground">{titulo}</h1>
      {(linea || empresa) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 texto-cuerpo text-foreground">
          {empresa && (
            // Con el nombre en el texto, el sello es solo la cara de la empresa y el lector de pantalla no lo repite.
            <span aria-hidden={empresa.logoLargo ? undefined : true} className="inline-flex">
              <MarcaEmpresaCompra empresa={empresa} />
            </span>
          )}
          {linea && <span>{linea}</span>}
        </p>
      )}
    </header>
  );
}
