// La regla de cobro por personas que se lee junto al contador del checkout: qué cubre el precio y qué cuesta
// sumar a alguien, dicha antes de cruzarla y en el momento de cruzarla (PFD, 2026-10-22). Módulo puro, sin
// imports: los montos llegan ya en la moneda de la página y `formatear` les pone el signo y la moneda.

export type ReglaPersonas =
  /** Un precio por grupo que cubre `incluidas` y suma `extra` por cada persona de más (0 = mismo precio). */
  | { tipo: 'grupo'; incluidas: number; extra: number; maximo: number }
  /** Un precio por cada persona. */
  | { tipo: 'persona'; precio: number }
  /** Tarifas por rango de pasajeros (traslados), ordenadas o no. */
  | { tipo: 'rangos'; rangos: { min: number; max: number; precio: number }[] }
  /** Dentro de un paquete: sumar a alguien a este servicio no cambia el precio. */
  | { tipo: 'incluido' };

export type TextosRegla = {
  /** «El precio cubre hasta {n} personas · desde la {m}.ª, +{precio} por persona» */
  grupoCubre: string;
  /** «Personas extra: {k} × {precio} = +{monto}» */
  grupoExtra: string;
  /** «Mismo precio de 1 a {max} personas» */
  grupoFijo: string;
  /** «{precio} por persona × {n} = {monto}» */
  persona: string;
  /** «{min}–{max} pasajeros: {precio}» */
  rango: string;
  /** «desde {k}: {precio}» */
  rangoSiguiente: string;
  /** «Incluido en el paquete, sin costo por persona» */
  incluido: string;
};

export function textoRegla(regla: ReglaPersonas, personas: number, formatear: (monto: number) => string, t: TextosRegla): string | null {
  switch (regla.tipo) {
    case 'grupo': {
      if (!(regla.extra > 0) || regla.incluidas >= regla.maximo) return t.grupoFijo.replace('{max}', String(regla.maximo));
      const extras = personas - regla.incluidas;
      if (extras <= 0) {
        return t.grupoCubre
          .replace('{n}', String(regla.incluidas))
          .replace('{m}', String(regla.incluidas + 1))
          .replace('{precio}', formatear(regla.extra));
      }
      return t.grupoExtra
        .replace('{k}', String(extras))
        .replace('{precio}', formatear(regla.extra))
        .replace('{monto}', formatear(regla.extra * extras));
    }
    case 'persona':
      return t.persona
        .replace('{precio}', formatear(regla.precio))
        .replace('{n}', String(personas))
        .replace('{monto}', formatear(regla.precio * personas));
    case 'rangos': {
      const rangos = [...regla.rangos].sort((a, b) => a.min - b.min);
      const actual = rangos.find((r) => personas >= r.min && personas <= r.max);
      if (!actual) return null;
      const base = t.rango
        .replace('{min}', String(actual.min))
        .replace('{max}', String(actual.max))
        .replace('{precio}', formatear(actual.precio));
      const siguiente = rangos.find((r) => r.min > actual.max && r.precio !== actual.precio);
      return siguiente
        ? `${base} · ${t.rangoSiguiente.replace('{k}', String(siguiente.min)).replace('{precio}', formatear(siguiente.precio))}`
        : base;
    }
    case 'incluido':
      return t.incluido;
  }
}
