import { notFound } from 'next/navigation';

/**
 * Ruta comodin para cualquier URL rota bajo /es o /en.
 *
 * Sin esto, `/es/lo-que-sea` no coincide con ninguna ruta y Next busca un
 * `not-found` en la raiz de `app/` — que aqui no existe, porque el layout raiz
 * es el de `[lang]`. Al hacer que la URL SI coincida y llamar a `notFound()`,
 * se renderiza `[lang]/not-found.tsx` y la respuesta sigue siendo 404 de verdad,
 * que es lo que necesitan los buscadores.
 */
export default function RutaInexistente() {
  notFound();
}
