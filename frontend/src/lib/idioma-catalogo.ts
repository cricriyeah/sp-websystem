// El nombre y la descripción de un servicio o paquete en el idioma de la página. El backoffice guarda el español
// en `nombre`/`descripcion` y el inglés en `nombre_en`/`descripcion_en`; si el inglés está vacío se queda el
// español. Se aplica una vez, al traer el catálogo, para que todo lo de abajo (tarjetas, detalle, checkout)
// use `nombre` y `descripcion` sin saber de idiomas. Módulo puro, sin imports: lo prueba el runner.

type Lang = 'es' | 'en';
type Extra = { nombre: string; nombre_en?: string };
type Traducible = {
  nombre: string; nombre_en?: string; descripcion?: string; descripcion_en?: string;
  // La ficha del servicio (duración y punto de salida) y los nombres de sus extras.
  duracion?: string; duracion_en?: string; punto_salida?: string; punto_salida_en?: string;
  personalizaciones?: Extra[];
};
type ConComponentes<S> = { servicios_asociados: { servicio: S }[] };

/** El inglés si lo hay; si no, el español. Solo para campos que el objeto trae. */
function campo<T extends Traducible>(objeto: T, es: 'descripcion' | 'duracion' | 'punto_salida') {
  if (objeto[es] === undefined) return {};
  const en = objeto[`${es}_en`]?.trim();
  return { [es]: en || objeto[es] };
}

export function enIdioma<T extends Traducible>(objeto: T, lang: Lang): T {
  if (lang !== 'en') return objeto;
  const nombre = objeto.nombre_en?.trim();
  return {
    ...objeto,
    nombre: nombre || objeto.nombre,
    ...campo(objeto, 'descripcion'),
    ...campo(objeto, 'duracion'),
    ...campo(objeto, 'punto_salida'),
    ...(objeto.personalizaciones
      ? { personalizaciones: objeto.personalizaciones.map((extra) => ({ ...extra, nombre: extra.nombre_en?.trim() || extra.nombre })) }
      : {}),
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
