'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useReducedMotion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Pause, Play } from '@phosphor-icons/react';
import { destinoDeFila, estadoDeFila, indiceDeFila, siguienteAutomatico, type EstadoFila } from '@/lib/fila-arrastrable';
import { Button } from './button';

type Props = {
  /** El encabezado de la fila (el `<h2>` de la sección); las flechas van a su derecha. */
  cabeza: ReactNode;
  /** Nombre accesible del carril: es una región que se enfoca y se recorre con el teclado. */
  etiqueta: string;
  textos: { anterior: string; siguiente: string; pausar?: string; reanudar?: string };
  /**
   * La fila avanza sola, una tarjeta cada `AVANCE_MS`, y del final vuelve al principio (reseñas, dueño 2026-11-12).
   * Lleva botón de pausa junto a las flechas (`textos.pausar`/`reanudar`) y no lleva el amago del teléfono.
   */
  automatico?: boolean;
  /** Las tarjetas: cada una crece (`flex-grow`) hasta llenar la fila cuando caben todas. */
  children: ReactNode;
};

// Cuánto se queda cada tarjeta en la fila automática; también lo que espera después de que el visitante la toca.
const AVANCE_MS = 5000;
const INICIAL: EstadoFila = { desborda: false, avance: 1, puedeAtras: false, puedeAdelante: false };
// El amago del teléfono: la fila se corre lo justo para que asome la orilla de la siguiente tarjeta, se detiene
// un instante y regresa asentándose. Cada tramo lleva su propia curva (la de la animación es lineal): sale
// acelerando y frenando, y vuelve con un pequeño rebase de 6 px, como si la soltara un resorte.
const AMAGO_PX = 64;
const AMAGO_MS = 1600;
const AMAGO_CUADROS: Keyframe[] = [
  { transform: 'translateX(0)', easing: 'cubic-bezier(0.45, 0, 0.2, 1)' },
  { transform: `translateX(-${AMAGO_PX}px)`, offset: 0.38 },
  { transform: `translateX(-${AMAGO_PX}px)`, offset: 0.5, easing: 'cubic-bezier(0.3, 0, 0.15, 1)' },
  { transform: 'translateX(6px)', offset: 0.84, easing: 'cubic-bezier(0.4, 0, 0.4, 1)' },
  { transform: 'translateX(0)' },
];

/**
 * Fila de tarjetas que se arrastra: carril con `scroll-snap` obligatorio (siempre se detiene en una tarjeta, nunca a la mitad de dos), flechas en círculo y una barra de avance de
 * 4 px. Las flechas van junto al título (en el teléfono con un contador «1 / 3» y un amago de deslizamiento la primera vez que se ve). Las flechas y la barra solo existen cuando la fila no cabe. Sin JavaScript sigue siendo un carril
 * que se desliza con el dedo. Con «reducir movimiento» las flechas saltan sin deslizar.
 *
 * Con `automatico` avanza sola mientras se ve. Se detiene con el botón de pausa, con la pestaña oculta y mientras el
 * foco del teclado está dentro (no el de un clic: en escritorio el clic en una flecha deja el foco ahí y la dejaba
 * quieta para siempre). Tampoco se detiene con el cursor encima: en escritorio la mano suele quedar sobre la fila y
 * parecía que no avanzaba (dueño, 2026-11-12). Después de que el visitante la desliza, la arrastra o usa una flecha,
 * espera una vuelta completa antes de seguir desde donde la dejó. Con «reducir movimiento» no se mueve sola.
 */
export function FilaArrastrable({ cabeza, etiqueta, textos, automatico = false, children }: Props) {
  const carril = useRef<HTMLDivElement>(null);
  const reducido = useReducedMotion();
  const [estado, setEstado] = useState<EstadoFila>(INICIAL);
  const [posicion, setPosicion] = useState({ actual: 0, total: 0 });
  const [pausada, setPausada] = useState(false);
  // Lo que detiene un momento la fila automática sin volver a pintar: foco de teclado dentro, si se ve y hasta
  // cuándo espera después de que el visitante la movió.
  const freno = useRef({ foco: false, visible: false, hasta: 0 });
  const tocada = () => { freno.current.hasta = Date.now() + AVANCE_MS; };

  const medir = useCallback(() => {
    const el = carril.current;
    if (!el) return;
    setEstado(estadoDeFila(el));
    const tarjetas = Array.from(el.children) as HTMLElement[];
    const origen = tarjetas[0]?.offsetLeft ?? 0;
    setPosicion({ actual: indiceDeFila(el.scrollLeft, tarjetas.map((t) => t.offsetLeft - origen)), total: tarjetas.length });
  }, []);

  // En el teléfono cada tarjeta ocupa la fila y la siguiente no asoma: la primera vez que la fila entra a la
  // pantalla se corre un poco y regresa, para enseñar que se desliza. Una vez por montaje, nunca con «reducir
  // movimiento», ni si ya se deslizó o no hay más tarjetas.
  useEffect(() => {
    const el = carril.current;
    if (!el || automatico || reducido || !window.matchMedia('(max-width: 639px)').matches) return;
    const observador = new IntersectionObserver(([entrada]) => {
      if (!entrada?.isIntersecting) return;
      observador.disconnect();
      if (el.scrollLeft > 2 || el.scrollWidth - el.clientWidth <= 2) return;
      el.animate(AMAGO_CUADROS, { duration: AMAGO_MS, delay: 400, easing: 'linear' });
    }, { threshold: 0.6 });
    observador.observe(el);
    return () => observador.disconnect();
  }, [automatico, reducido]);

  const desborda = estado.desborda;
  useEffect(() => {
    const el = carril.current;
    if (!el || !automatico || reducido || pausada || !desborda) return;
    const observador = new IntersectionObserver(([entrada]) => { freno.current.visible = !!entrada?.isIntersecting; }, { threshold: 0.5 });
    observador.observe(el);
    const reloj = window.setInterval(() => {
      const f = freno.current;
      if (!f.visible || f.foco || document.hidden || Date.now() < f.hasta) return;
      const tarjetas = Array.from(el.children) as HTMLElement[];
      const origen = tarjetas[0]?.offsetLeft ?? 0;
      const inicios = tarjetas.map((t) => t.offsetLeft - origen);
      el.scrollTo({ left: siguienteAutomatico(el.scrollLeft, inicios, el.scrollWidth - el.clientWidth), behavior: 'smooth' });
    }, AVANCE_MS);
    return () => {
      observador.disconnect();
      window.clearInterval(reloj);
    };
  }, [automatico, reducido, pausada, desborda]);

  useEffect(() => {
    const el = carril.current;
    if (!el) return;
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(el);
    for (const hijo of Array.from(el.children)) observador.observe(hijo);
    return () => observador.disconnect();
  }, [medir]);

  const mover = (sentido: -1 | 1) => {
    const el = carril.current;
    tocada();
    if (el) el.scrollTo({ left: destinoDeFila(el, sentido), behavior: reducido ? 'auto' : 'smooth' });
  };
  const conPausa = automatico && !reducido && textos.pausar && textos.reanudar;

  const flechas = (
    <>
      {conPausa && (
        <Button variante="campana-gris" tamano="icono" aria-label={pausada ? textos.reanudar : textos.pausar} aria-pressed={pausada} onClick={() => setPausada((p) => !p)}>
          {pausada ? <Play size={20} weight="bold" aria-hidden="true" /> : <Pause size={20} weight="bold" aria-hidden="true" />}
        </Button>
      )}
      <Button variante="campana-gris" tamano="icono" aria-label={textos.anterior} aria-disabled={!estado.puedeAtras} onClick={() => mover(-1)}>
        <ArrowLeft size={20} weight="bold" aria-hidden="true" />
      </Button>
      <Button variante="campana-gris" tamano="icono" aria-label={textos.siguiente} aria-disabled={!estado.puedeAdelante} onClick={() => mover(1)}>
        <ArrowRight size={20} weight="bold" aria-hidden="true" />
      </Button>
    </>
  );

  return (
    <div
      onFocus={(e) => { freno.current.foco = e.target.matches(':focus-visible'); }}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) freno.current.foco = false; }}
    >
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-end justify-between gap-6 px-pagina pb-8">
        {cabeza}
        {/* Junto al título, donde ya va la vista al llegar a la sección; en el teléfono con el contador «1 / 3»
            (las tarjetas ocupan la fila y nada más dice que hay otras). */}
        {estado.desborda && (
          <div className="flex items-center gap-2 max-sm:ml-auto">
            <span className="mr-2 texto-pequeno font-semibold tabular-nums text-foreground sm:hidden" aria-hidden="true">
              {posicion.actual + 1} / {posicion.total}
            </span>
            {flechas}
          </div>
        )}
      </div>
      <div
        ref={carril}
        role="region"
        aria-label={etiqueta}
        tabIndex={0}
        onScroll={medir}
        onPointerDown={tocada}
        onWheel={(e) => { if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) tocada(); }}
        onKeyDown={tocada}
        className="mx-auto flex max-w-[1440px] snap-x snap-mandatory gap-4 overflow-x-auto sm:gap-3 scroll-px-pagina px-pagina pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>
      {estado.desborda && (
        <div className="mx-auto mt-7 flex max-w-[1440px] items-center gap-4 px-pagina">
          <div aria-hidden="true" className="h-1 flex-1 overflow-hidden bg-cafe-bruma">
            <span
              className="block h-full origin-left bg-tinta transition-transform duration-[120ms] ease-linear motion-reduce:transition-none"
              style={{ transform: `scaleX(${estado.avance})` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
