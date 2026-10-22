// Descripción corta de la tarjeta de un servicio o paquete en «Reserva ahora mismo», por clave de catálogo
// (`servicio:<empresa>/<slug>`, como `imagenes-catalogo.ts`). Es texto de venta del sitio, en los dos idiomas;
// lo que no está aquí sale sin descripción. Solo datos reales del servicio: nada de cifras inventadas.

type Lang = 'es' | 'en';

const DESCRIPCIONES: Record<string, Record<Lang, string>> = {
  'servicio:sal-y-sol/pesca-deportiva': {
    es: 'La panga entera para tu grupo, saliendo al amanecer en busca de marlín, dorado o jurel según la temporada. Desayuno ligero, comida, fruta, botanas y bebidas van a bordo: tú solo pones las ganas de pescar.',
    en: 'The whole panga for your group, heading out at dawn after marlin, mahi or yellowtail depending on the season. Light breakfast, lunch, fruit, snacks and drinks are on board: you just bring the urge to fish.',
  },
};

export function descripcionDeCatalogo(clave: string, lang: Lang): string | null {
  return DESCRIPCIONES[clave]?.[lang] ?? null;
}
