'use client';

import type { ReactNode } from 'react';
import { LazyMotion, domAnimation } from 'framer-motion';

/**
 * Proveedor de motion para todo el sitio. Los componentes pintan con `m.*` (no
 * con `motion.*`) y este proveedor les da las funciones: `domAnimation` cubre
 * animate/exit/variants y los gestos hover, tap y focus. No incluye `drag` ni
 * `layout`; el que los use (hoy solo el mapa de sedes) anida su propio
 * `<LazyMotion features={domMax} strict>`.
 *
 * `domAnimation` se importa SINCRONO, no con `import()` diferido. Es una
 * excepcion deliberada a `bundle-dynamic-imports`: con la carga diferida, la
 * primera animacion que se dispara antes de que llegue el paquete (el aviso de
 * cookies, el menu del header) aparece de golpe en vez de animarse.
 *
 * `strict` lanza error en desarrollo si algun componente usa `motion.*` en vez
 * de `m.*`. En produccion un `motion.*` suelto compila y pierde el ahorro de
 * peso; por eso la regla `motion-completo` de la compuerta (scripts/guardia-estilos.cjs)
 * lo cuenta y debe seguir en 0.
 *
 * Todo se importa de `framer-motion`, NO de `motion/react`. Ese reexporte hace
 * `const motion = fm.motion` a nivel de modulo y Turbopack no lo descarta: con
 * cualquier import de `motion/react` el componente `motion` completo (con
 * drag y layout) viaja aunque nadie lo use. Medido: `motion/react` + LazyMotion
 * subia ~9 KB en cada ruta; `framer-motion` + LazyMotion baja ~41 KB.
 * `framer-motion` es la misma version que trae `motion` y esta declarado en
 * package.json por eso.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      {children}
    </LazyMotion>
  );
}
