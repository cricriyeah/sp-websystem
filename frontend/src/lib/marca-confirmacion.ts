// Cuándo se muestra la confirmación de una reserva ya pagada.
//
// La pestaña recuerda el `checkout_id` de la última compra en sessionStorage. Sin más, entrar a /reservar
// desde cualquier lado, incluso para comprar de nuevo, reponía esa confirmación en lugar del formulario.
// Ahora la confirmación solo se muestra si la URL lo dice con `?confirmacion=1`: la pone la propia página
// al confirmar (una recarga o el botón Atrás vuelven a verla) y el botón «Ver confirmación» de la banda
// «Continuar reservación». Cualquier otra entrada, sin la marca, abre un formulario nuevo.

export const PARAM_CONFIRMACION = 'confirmacion';

/** ¿La búsqueda de la URL (`?a=1&b=2` o `a=1`) pide ver la confirmación? */
export function tieneMarcaDeConfirmacion(search: string): boolean {
  return new URLSearchParams(search).get(PARAM_CONFIRMACION) === '1';
}

/** La misma ruta con la marca puesta: pathname + search, sin origen. */
export function conMarcaDeConfirmacion(ruta: string): string {
  const [sinHash, hash = ''] = ruta.split('#');
  const [camino, query = ''] = sinHash.split('?');
  const params = new URLSearchParams(query);
  params.set(PARAM_CONFIRMACION, '1');
  return `${camino}?${params.toString()}${hash ? `#${hash}` : ''}`;
}

/** En el navegador: ¿esta página se abrió pidiendo la confirmación? */
export function paginaPideConfirmacion(): boolean {
  return typeof window !== 'undefined' && tieneMarcaDeConfirmacion(window.location.search);
}

/** Deja la marca en la URL de esta página sin navegar ni sumar una entrada al historial. */
export function marcarPaginaComoConfirmacion(): void {
  if (typeof window === 'undefined' || paginaPideConfirmacion()) return;
  const destino = conMarcaDeConfirmacion(window.location.pathname + window.location.search + window.location.hash);
  window.history.replaceState(window.history.state, '', destino);
}
