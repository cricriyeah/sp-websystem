// Módulo puro, SIN imports (lo compila el runner de pruebas).

export type CapitanDeLista = { nombre: string; foto?: string; pendiente?: boolean };

/**
 * Los capitanes que se pintan. Un capitán `pendiente` es relleno (nombre o foto que el dueño aún no confirma): se ve en
 * desarrollo y en una vista previa que lo pida, pero NUNCA en el sitio publicado, para que «Capitán 3» no llegue a un
 * cliente. Si no queda ninguno, la lista es vacía y quien la pinta omite el bloque entero.
 */
export function capitanesVisibles<T extends CapitanDeLista>(lista: readonly T[], mostrarPendientes: boolean): T[] {
  return lista.filter((capitan) => mostrarPendientes || !capitan.pendiente);
}

/** Entorno de ejecución: relleno visible solo fuera de producción o con `NEXT_PUBLIC_VER_PENDIENTES=1`. */
export function mostrarPendientesEnEsteEntorno(entorno: { NODE_ENV?: string; NEXT_PUBLIC_VER_PENDIENTES?: string }): boolean {
  return entorno.NODE_ENV !== 'production' || entorno.NEXT_PUBLIC_VER_PENDIENTES === '1';
}
