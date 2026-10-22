// El nombre y la descripción de un servicio o paquete en el idioma de la página. El backoffice guarda el español
// en `nombre`/`descripcion` y el inglés en `nombre_en`/`descripcion_en`; si el inglés está vacío se queda el
// español. Se aplica una vez, al traer el catálogo, para que todo lo de abajo (tarjetas, detalle, checkout)
// use `nombre` y `descripcion` sin saber de idiomas. Módulo puro, sin imports: lo prueba el runner.

type Lang = 'es' | 'en';
type Traducible = { nombre: string; nombre_en?: string; descripcion?: string; descripcion_en?: string };
type ConComponentes<S> = { servicios_asociados: { servicio: S }[] };

export function enIdioma<T extends Traducible>(objeto: T, lang: Lang): T {
  if (lang !== 'en') return objeto;
  const nombre = objeto.nombre_en?.trim();
  const descripcion = objeto.descripcion_en?.trim();
  return {
    ...objeto,
    nombre: nombre || objeto.nombre,
    ...(objeto.descripcion !== undefined ? { descripcion: descripcion || objeto.descripcion } : {}),
  };
}

/** El paquete y los servicios que lo componen. */
export function paqueteEnIdioma<S extends Traducible, P extends Traducible & ConComponentes<S>>(paquete: P, lang: Lang): P {
  if (lang !== 'en') return paquete;
  return {
    ...enIdioma(paquete, lang),
    servicios_asociados: paquete.servicios_asociados.map((c) => ({ ...c, servicio: enIdioma(c.servicio, lang) })),
  };
}
