export type TipoInteraccion = 'check' | 'input_texto' | 'input_numero' | 'input_seleccion';

export type PersonalizacionUI = {
  id: number;
  nombre: string;
  tipo_interaccion: TipoInteraccion;
  opciones_seleccion: string[];
  aviso_reforzado: boolean;
  obligatorio: boolean;
  preseleccionado: boolean;
  cobrar_por_persona: boolean;
  cantidad_editable: boolean;
  precio: string;
  precio_usd: string | null;
};

export type SeleccionPersonalizacion = { id: number; cantidad?: number; respuesta?: string };

export const seleccionInicial = (catalogo: PersonalizacionUI[]): SeleccionPersonalizacion[] =>
  catalogo
    .filter((p) => p.tipo_interaccion === 'check' && p.preseleccionado)
    .map((p) => ({ id: p.id, cantidad: 1 }));

export function cantidadEfectiva(p: PersonalizacionUI, personas: number, cantidad = 1) {
  return !p.cobrar_por_persona
    ? 1
    : !p.cantidad_editable
      ? personas
      : Math.max(1, Math.min(cantidad, personas));
}

export function erroresPersonalizaciones(
  catalogo: PersonalizacionUI[],
  seleccion: SeleccionPersonalizacion[],
) {
  const errores: Record<number, 'required' | 'number' | 'selection'> = {};
  const elegidas = new Map(seleccion.map((s) => [s.id, s]));
  for (const p of catalogo) {
    if (p.tipo_interaccion === 'check') continue;
    const valor = elegidas.get(p.id)?.respuesta ?? '';
    if (!valor.trim()) {
      if (p.obligatorio) errores[p.id] = 'required';
      continue;
    }
    if (
      p.tipo_interaccion === 'input_numero' &&
      (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(valor.trim()) ||
        !Number.isFinite(Number(valor)))
    ) {
      errores[p.id] = 'number';
    }
    if (
      p.tipo_interaccion === 'input_seleccion' &&
      !p.opciones_seleccion.includes(valor)
    ) {
      errores[p.id] = 'selection';
    }
  }
  return errores;
}

export function totalPersonalizaciones(
  catalogo: PersonalizacionUI[],
  seleccion: SeleccionPersonalizacion[],
  personas: number,
  moneda: 'MXN' | 'USD',
): number | null {
  const elegidas = new Map(seleccion.map((s) => [s.id, s]));
  let centavos = 0;
  for (const p of catalogo) {
    const s = elegidas.get(p.id);
    if (!s || p.tipo_interaccion !== 'check') continue;
    const precio = moneda === 'USD' ? p.precio_usd : p.precio;
    if (precio === null || !Number.isFinite(Number(precio))) return null;
    centavos +=
      Math.round(Number(precio) * 100) * cantidadEfectiva(p, personas, s.cantidad);
  }
  return centavos / 100;
}
