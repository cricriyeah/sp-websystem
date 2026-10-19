import type { Dictionary } from '@/app/[lang]/dictionaries';

type TituloPagina = Dictionary['checkout']['tituloPagina'];

/** Clave del título fijo de la página de compra según el tipo de servicio del catálogo. */
export function claveTituloCompra(tipoServicio?: string | null): keyof TituloPagina {
  if (tipoServicio === 'hospedaje') return 'hospedaje';
  if (tipoServicio === 'transporte') return 'transporte';
  if (tipoServicio === 'paseo' || tipoServicio === 'bajo_demanda') return 'paseo';
  return 'pesca';
}

/**
 * Título fijo por tipo de compra («Reserva tu pesca»): no depende del largo del nombre del
 * producto, que a 36 px podía ocupar tres renglones o más. El producto, la sede y las
 * empresas pasan a una línea pequeña debajo.
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
      {detalle && <p className="mt-2 texto-pequeno text-muted">{detalle}</p>}
    </header>
  );
}
