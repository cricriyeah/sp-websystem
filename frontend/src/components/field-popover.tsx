'use client';

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

type FieldPopoverProps = {
  label: string;
  value: string;
  icon: ReactNode;
  /** Recibe `cerrar` para que al elegir una opcion el panel se cierre solo. */
  children: (cerrar: () => void) => ReactNode;
  /**
   * Contador para pedir apertura desde fuera. Al incrementarlo, el panel se
   * abre. Lo usa la barra de reserva para encadenar las preguntas: contestar
   * "cuantos son" abre sola la de "que dia".
   *
   * Es un contador y no un booleano a proposito: permite volver a pedir la
   * apertura del mismo campo mas de una vez sin tener que bajarlo primero.
   */
  solicitarApertura?: number;
  /** Sin respuesta todavia: la pregunta se muestra grande y sola. */
  vacio?: boolean;
  /** Texto grande cuando esta vacio (la pregunta). */
  placeholder?: string;
};

/** Margen contra el borde del viewport, y separacion entre el campo y el panel. */
const MARGEN_VIEWPORT = 16;
const SEPARACION = 8;
/** Bajo este espacio disponible abajo, se prefiere abrir hacia arriba (si ahi hay mas sitio). */
const ESPACIO_MINIMO_ABAJO = 220;
/** El panel nunca se aplasta mas de esto, aunque el viewport sea muy bajo. */
const ALTO_MINIMO = 160;

/**
 * Medir el campo toca un ref, y eso solo se puede hacer despues del render. En
 * el navegador va como efecto de layout —corre antes de pintar, asi que el
 * panel sale ya colocado en el mismo cuadro— y en el servidor cae a `useEffect`
 * para no disparar el aviso de React (donde no hay layout que medir).
 */
const useEfectoDeLayout = typeof window === 'undefined' ? useEffect : useLayoutEffect;

type Posicion = {
  haciaArriba: boolean;
  maxHeight: number;
};

/**
 * Campo del booking bar que abre un panel: se usa para el calendario y para la
 * hora. Reemplaza a `<input type="date">` y `<select>`, cuyos desplegables los
 * pinta el sistema operativo y no se pueden llevar al diseño del sitio.
 *
 * **El panel es `absolute`, anclado al campo.** Estuvo un rato como `fixed` con
 * coordenadas del viewport calculadas al abrir, y eso lo despegaba de la barra:
 * al hacer scroll con el panel abierto, el panel se quedaba clavado en la
 * pantalla mientras la barra se iba. Anclado al campo, el navegador lo mueve
 * junto con la barra sin que haya que recalcular nada en cada cuadro de scroll.
 *
 * Lo que si se mide en el viewport es **de que lado abrir y cuanto puede medir**:
 * cuanto sitio real hay arriba y abajo del campo en el momento de abrir. Antes
 * eso era una constante adivinada (`alturaEstimada`) que se comparaba contra el
 * espacio de abajo, y ademas recortaba el panel a esa misma cifra: cuando el
 * contenido real media mas —el mes largo del calendario— abria hacia el lado
 * equivocado y encima salia cortado.
 *
 * Se encarga de lo aburrido pero necesario: cerrar al hacer clic fuera, cerrar
 * con Escape, y devolver el foco al boton para que se pueda usar con teclado.
 */
export function FieldPopover({
  label,
  value,
  icon,
  children,
  solicitarApertura = 0,
  vacio = false,
  placeholder,
}: FieldPopoverProps) {
  const [open, setOpen] = useState(false);
  const [posicion, setPosicion] = useState<Posicion | null>(null);
  const contenedor = useRef<HTMLDivElement>(null);
  const disparador = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const sinMovimiento = useReducedMotion();

  /**
   * Mide el espacio real del viewport arriba y abajo del campo, y decide lado
   * y alto maximo a partir de eso — no de una adivinanza del contenido.
   */
  const calcularPosicion = (): Posicion | null => {
    const caja = disparador.current?.getBoundingClientRect();
    if (!caja) return null;

    const espacioAbajo = window.innerHeight - caja.bottom - MARGEN_VIEWPORT - SEPARACION;
    const espacioArriba = caja.top - MARGEN_VIEWPORT - SEPARACION;
    const haciaArriba = espacioAbajo < ESPACIO_MINIMO_ABAJO && espacioArriba > espacioAbajo;

    return {
      haciaArriba,
      maxHeight: Math.max(ALTO_MINIMO, haciaArriba ? espacioArriba : espacioAbajo),
    };
  };

  const alternar = () => setOpen((v) => !v);

  // Solo cambia estado: se lo pasamos a `children`, que corre en render, y una
  // funcion que tocara refs ahi dentro dispara la regla react-hooks/refs.
  const cerrar = () => setOpen(false);

  // Apertura pedida desde fuera. Va como ajuste durante el render y no en un
  // efecto: asi el panel ya sale abierto en el mismo pintado, sin el parpadeo de
  // verlo cerrado un cuadro.
  const [aperturaVista, setAperturaVista] = useState(solicitarApertura);
  if (solicitarApertura !== aperturaVista) {
    setAperturaVista(solicitarApertura);
    if (solicitarApertura > 0) setOpen(true);
  }

  // La medida se toma aqui y no al abrir: leer el ref durante el render devuelve
  // la caja del cuadro anterior y ademas React lo prohibe. Como el panel solo se
  // pinta con `posicion` ya calculada, esto corre antes del primer pintado con
  // el panel visible: no hay parpadeo ni salto de lado.
  useEfectoDeLayout(() => {
    if (open) setPosicion(calcularPosicion());
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const alClicFuera = (event: PointerEvent) => {
      if (!contenedor.current?.contains(event.target as Node)) setOpen(false);
    };
    // Escape devuelve el foco al boton para no dejar al usuario de teclado
    // perdido al final del documento. Al hacer clic fuera no: ahi el foco ya es
    // de donde el usuario decidio ir.
    const alTeclear = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        disparador.current?.focus();
      }
    };
    // El panel esta anclado al campo, asi que el scroll no lo despega — pero si
    // puede dejarlo abriendo hacia un lado que ya no es el que mas sitio tiene.
    // Se vuelve a medir en vez de cerrar: cerrarle el calendario en la cara a
    // quien solo movio la rueda es peor que un panel que se reacomoda.
    const alDesplazar = () => setPosicion(calcularPosicion());

    document.addEventListener('pointerdown', alClicFuera);
    document.addEventListener('keydown', alTeclear);
    window.addEventListener('scroll', alDesplazar, { passive: true });
    window.addEventListener('resize', alDesplazar);
    return () => {
      document.removeEventListener('pointerdown', alClicFuera);
      document.removeEventListener('keydown', alTeclear);
      window.removeEventListener('scroll', alDesplazar);
      window.removeEventListener('resize', alDesplazar);
    };
    // `calcularPosicion` se redefine en cada render y no guarda estado: incluirla
    // solo volveria a montar los listeners sin cambiar lo que hacen.
  }, [open]);

  return (
    <div ref={contenedor} className="relative flex flex-1">
      <button
        ref={disparador}
        type="button"
        onClick={alternar}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        className="flex flex-1 items-center gap-3 px-6 py-3.5 text-left transition-colors hover:bg-background"
      >
        {icon}
        {/* Sin contestar, la pregunta ocupa el lugar grande y no hay etiqueta
            chica: no tiene sentido rotular un dato que todavia no existe. Al
            contestar, la pregunta se encoge y la respuesta toma su lugar — asi
            cada respuesta se vuelve un compromiso visible.

            El alto va fijo (`h-10`) y no lo pone el contenido: sin eso, aparecer
            la etiqueta al contestar sumaba una linea y **la barra entera crecia
            de golpe** en mitad del flujo. Con el alto reservado, el contenido se
            centra mientras esta vacio y se acomoda al contestar, sin mover nada
            de lo que hay alrededor. */}
        <span className="flex h-10 flex-col items-start justify-center gap-0.5">
          {!vacio && <span className="text-xs text-muted">{label}</span>}
          <span
            className={`whitespace-nowrap ${
              vacio ? 'text-sm font-medium text-foreground/70' : 'text-sm text-foreground'
            }`}
          >
            {vacio ? placeholder : value}
          </span>
        </span>
      </button>

      <AnimatePresence>
        {open && posicion && (
          <motion.div
            key="panel"
            id={panelId}
            role="dialog"
            aria-label={label}
            initial={
              sinMovimiento
                ? { opacity: 0 }
                : { opacity: 0, scale: 0.97, y: posicion.haciaArriba ? 6 : -6 }
            }
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={
              sinMovimiento
                ? { opacity: 0 }
                : { opacity: 0, scale: 0.97, y: posicion.haciaArriba ? 6 : -6 }
            }
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            style={{ maxHeight: posicion.maxHeight }}
            // `w-full` en movil: el campo ya ocupa toda la tarjeta ahi (los campos
            // se apilan), asi que el panel toma su mismo ancho — antes el
            // contenido (`w-72`/`w-56` en date-field/time-field) mandaba su
            // propio ancho fijo y quedaba angosto y descentrado contra la
            // tarjeta. Desde `sm:` el campo vuelve a ser un tercio de la barra y
            // ahi si conviene que el panel se encoja a lo que pida su contenido.
            className={`absolute left-0 z-30 w-full overflow-y-auto border border-border bg-surface p-4 text-left shadow-[0_16px_40px_rgba(11,36,32,0.18)] sm:w-auto ${
              posicion.haciaArriba ? 'bottom-full mb-2 origin-bottom' : 'top-full mt-2 origin-top'
            }`}
          >
            {children(cerrar)}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
