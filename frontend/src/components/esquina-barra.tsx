'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { CaretLeft } from '@phosphor-icons/react';
import { AnimatePresence, m, useReducedMotion, type Transition } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';
import { Flama, LogoMarca } from '@/components/barra-flotante';

const MARCA = 'Sun Baja Experience';

/** A dónde vuelve la esquina: un enlace (`href`) o un paso del checkout (`alPulsar`). */
export type DestinoEsquina = {
  /** El nombre corto que ocupa el hueco de las letras del logo («La Paz», «Destinos», «Paso anterior»). */
  etiqueta: string;
  /** Lo que lee el lector de pantalla («Volver a La Paz»). */
  aria: string;
  href?: string;
  alPulsar?: () => void;
  /** Lleva al inicio: en modo «solo sede» la esquina vuelve a ser el logo, que ahí lleva a la sede. */
  soloHub?: boolean;
};

type Props = {
  /** `null` en el inicio: la esquina es la marca de siempre (flama + letras). */
  regreso: DestinoEsquina | null;
  /** A dónde lleva la marca cuando la esquina es el logo. Sin él la marca no es enlace (checkout con dinero retenido). */
  hrefLogo?: string;
  /** Se llama al tocar cualquiera de las dos (cierra el menú móvil). */
  alPulsar?: () => void;
  /** El menú móvil abierto gira la flama media vuelta. */
  girado?: boolean;
  /** Milisegundos que espera la entrada (la de la flama y la del nombre), como en `LogoMarca`. */
  retraso?: number;
};

// Lo que mostraba la esquina en la página anterior de esta pestaña (`true`: ya había «‹»). Vive en memoria: una carga
// entera lo borra y en el servidor nunca se escribe (solo cambia en un efecto), así que no altera la hidratación.
let yaHabiaRegreso = false;

// Resorte críticamente amortiguado (Apple: damping 1.0, response ~0.35 s): llega sin rebotar.
const RESORTE: Transition = { type: 'spring', bounce: 0, duration: 0.35 };
// Las letras del logo entran a los 750 ms (`.logo-letras-barra`): el nombre llega a la misma hora y en el mismo sitio.
const ENTRADA_NOMBRE_S = 0.75;
// La flama ya se ve hacia los 600 ms de su giro: el «‹» llega un poco antes, desde la izquierda.
const ENTRADA_FLECHA_S = 0.5;

/**
 * La esquina izquierda de la barra flotante (PFD + principios de Apple, 2026-11-17): el logo es el regreso, sin alto
 * extra. En el inicio es la marca (flama + letras «SBE») y lleva al inicio. En cualquier otra página es UN solo enlace,
 * «‹ + flama + nombre corto del destino», al destino de `lib/regreso.ts` (o al paso anterior del checkout).
 *
 * Modo «solo sede»: si el destino es el inicio (`soloHub`), la esquina sigue siendo el logo, que en ese modo lleva a la
 * sede. La cookie solo se lee en el cliente, así que se pintan las dos variantes y el CSS esconde la que no toca antes
 * de pintar (`sale-al-hub` / `solo-en-sede`, globals.css, por `data-solo-sede` en `<body>`): sin parpadeo.
 */
export function EsquinaBarra({ regreso, hrefLogo, alPulsar, girado = false, retraso = 0 }: Props) {
  const conRegreso = Boolean(regreso);
  useEffect(() => { yaHabiaRegreso = conRegreso; }, [conRegreso]);

  const marca = <LogoMarca girado={girado} retraso={retraso} />;
  const logo = hrefLogo ? (
    <Link href={hrefLogo} className={FOCO} onClick={alPulsar} aria-label={MARCA}>{marca}</Link>
  ) : marca;
  if (!regreso) return logo;

  const pieza = <PiezaRegreso destino={regreso} alPulsar={alPulsar} girado={girado} retraso={retraso} />;
  if (!regreso.soloHub) return pieza;
  return (
    <>
      <span className="sale-al-hub inline-flex">{pieza}</span>
      <span className="solo-en-sede">{logo}</span>
    </>
  );
}

const FOCO = 'inline-flex rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring';

type PiezaProps = { destino: DestinoEsquina; alPulsar?: () => void; girado: boolean; retraso: number };

function PiezaRegreso({ destino, alPulsar, girado, retraso }: PiezaProps) {
  const sinMovimiento = useReducedMotion();
  // Si la página anterior ya tenía «‹», se queda quieto donde estaba; si venía del logo (inicio, primera carga), entra.
  const [flechaEntra] = useState(() => !yaHabiaRegreso);
  // Solo la primera aparición del nombre espera a que la barra se abra; un cambio después (el paso del checkout, la
  // página anterior de una legal que se lee al montar) es un fundido en el sitio, sin espera.
  const [asentado, setAsentado] = useState(false);
  const espera = retraso / 1000;
  // Con «reducir movimiento» nada viaja: solo opacidad. El `initial` es el mismo para no cambiar el HTML del servidor.
  const viaje = (retardo: number): Transition => (sinMovimiento ? { duration: 0 } : { ...RESORTE, delay: retardo });
  const fundido = (retardo: number, duracion = 0.25): Transition => ({ duration: duracion, ease: 'easeOut', delay: retardo });
  const esperaNombre = asentado ? 0 : ENTRADA_NOMBRE_S + espera;
  // En la letra de los titulares (monoespaciada, ~0.54 em por letra con su tracking) caben 10 letras a 20 px en los
  // 112 px que deja la barra a 390 px: «LA VENTANA» va en una línea (dueño, 2026-11-17). Una palabra de más de 9 letras
  // («DESTINATIONS») baja a 16; dos palabras que no caben en una línea («PUERTO CHALE», «PASO ANTERIOR») se apilan.
  const palabraLarga = Math.max(...destino.etiqueta.split(/\s+/).map((p) => p.length)) > 9;

  const contenido: ReactNode = (
    // Al presionar baja a 0.97 en el momento (pointer-down), no al soltar; con «reducir movimiento», solo se aclara.
    <m.span
      className="flex h-11 items-center"
      whileTap={sinMovimiento ? { opacity: 0.7 } : { scale: 0.97 }}
      transition={{ type: 'spring', bounce: 0, duration: 0.2 }}
    >
      {/* El trazo del «‹» ocupa solo un tercio de su ícono: la casilla de 12 px recorta el aire de los lados, así el
          trazo queda a la misma distancia del borde de la píldora que el botón del menú del otro lado. */}
      <m.span
        aria-hidden="true"
        className="mr-1 inline-flex w-3 shrink-0 justify-center text-foreground"
        initial={flechaEntra ? { opacity: 0, x: -10 } : false}
        animate={{ opacity: 1, x: 0 }}
        transition={{ x: viaje(ENTRADA_FLECHA_S + espera), opacity: fundido(ENTRADA_FLECHA_S + espera) }}
      >
        <CaretLeft size={20} weight="bold" className="shrink-0" />
      </m.span>
      <Flama girado={girado} retraso={retraso} />
      {/* Las dos etiquetas comparten la casilla mientras una se va y la otra llega: el ancho no brinca a media mitad. */}
      <span className="ml-2 grid min-w-0 items-center">
        <AnimatePresence initial>
          <m.span
            key={destino.etiqueta}
            className={cn(
              '[grid-area:1/1] max-w-[7rem] texto-mono-mayus font-bold leading-[0.9] tracking-[-0.05em] text-foreground [text-wrap:balance] transition-colors group-hover:text-cafe',
              palabraLarga ? 'text-[16px]' : 'text-[20px]',
            )}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, transition: fundido(0, 0.15) }}
            transition={{ x: viaje(esperaNombre), opacity: fundido(esperaNombre, 0.3) }}
            onAnimationComplete={() => setAsentado(true)}
          >
            {destino.etiqueta}
          </m.span>
        </AnimatePresence>
      </span>
    </m.span>
  );

  const clases = `group ${FOCO}`;
  if (destino.alPulsar) {
    const pulsar = destino.alPulsar;
    return (
      <Button variante="libre" type="button" aria-label={destino.aria} className={clases} onClick={() => { alPulsar?.(); pulsar(); }}>
        {contenido}
      </Button>
    );
  }
  return (
    <Link href={destino.href ?? '/'} aria-label={destino.aria} className={clases} onClick={alPulsar}>
      {contenido}
    </Link>
  );
}
