'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react';
import { useReducedMotion } from 'framer-motion';
import { cn } from '@/components/ui/cn';
import { botonClases } from '@/components/ui/variantes';

type Props = {
  /** Las secciones navegables que de verdad se pintan (`enlacesDeSede`), con su etiqueta ya resuelta. */
  anclas: { ancla: string; etiqueta: string }[];
  /** Nombre accesible de la barra de secciones. */
  etiqueta: string;
  /** El botón fijo del teléfono: a dónde baja, qué dice y el «desde» del producto que abre la fila (si tiene precio). */
  reservar: { ancla: string; texto: string; desde: string | null };
  /** Mientras alguna de estas secciones se ve, el botón fijo se esconde: ya está la compra en pantalla. */
  compra: string[];
};

/**
 * La navegación de la página de sede (PFD, 2026-11-17), para quien llega acostumbrado a GetYourGuide o Airbnb:
 *
 * - **Barra de secciones** (teléfono y tablet; desde 1280 px las secciones ya van en la barra de arriba): fija bajo la
 *   barra de arriba. Aparece cuando el héroe ya salió de pantalla (en el héroe no suma alto: el dueño ya rechazó un
 *   renglón extra ahí). Al aparecer escribe `--secciones-alto`, que `html` usa como `scroll-padding-top`, así un salto a
 *   una sección no deja su título debajo de las pastillas.
 *   Forma (2026-11-17): pastillas sueltas (blancas; la de la sección actual, negra). El dueño rechazó meterlas en una
 *   bandeja blanca como la barra. Para que no se corten en seco contra la pantalla, el carril va de orilla a orilla, la
 *   primera arranca en el margen de la página y, solo del lado donde quedan más, el borde se desvanece (máscara sobre el
 *   contenido, no un degradado pintado).
 * - **Botón fijo**: «Desde $X · Ver qué reservar», solo cuando ninguna sección de compra está a la vista. En el teléfono
 *   ocupa el ancho de abajo; desde 640 px (dueño, 2026-11-17) es una píldora flotante abajo a la derecha, con la sombra
 *   de la barra de arriba porque de verdad flota sobre la página.
 *
 * Se monta justo después del héroe: su marcador en el flujo es lo que dice si el héroe ya pasó. Sin JavaScript no
 * pinta nada (los enlaces siguen en el menú y en el pie).
 */
export function NavegacionSede({ anclas, etiqueta, reservar, compra }: Props) {
  const marcador = useRef<HTMLDivElement>(null);
  const carril = useRef<HTMLUListElement>(null);
  const [trasHeroe, setTrasHeroe] = useState(false);
  const [actual, setActual] = useState<string | null>(null);
  const [compraVisible, setCompraVisible] = useState(false);
  const [bordes, setBordes] = useState({ izquierda: false, derecha: false });
  const sinMovimiento = useReducedMotion();

  // Qué lados del carril esconden pastillas: solo ahí se desvanece el borde.
  const medirBordes = useCallback(() => {
    const lista = carril.current;
    if (!lista) return;
    const izquierda = lista.scrollLeft > 2;
    const derecha = lista.scrollLeft + lista.clientWidth < lista.scrollWidth - 2;
    setBordes((antes) => (antes.izquierda === izquierda && antes.derecha === derecha ? antes : { izquierda, derecha }));
  }, []);
  useEffect(() => {
    medirBordes();
    window.addEventListener('resize', medirBordes);
    return () => window.removeEventListener('resize', medirBordes);
  }, [medirBordes, trasHeroe]);

  // El héroe pasó cuando el marcador (justo bajo él) sube por encima de la barra de arriba.
  useEffect(() => {
    const elemento = marcador.current;
    if (!elemento) return;
    const observador = new IntersectionObserver(
      ([entrada]) => setTrasHeroe(!entrada.isIntersecting && entrada.boundingClientRect.top < 0),
      { threshold: 0 },
    );
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  // La sección que se lee: la que cruza una franja a un tercio de la pantalla.
  useEffect(() => {
    const secciones = anclas
      .map((a) => document.getElementById(a.ancla.replace(/^#/, '')))
      .filter((s): s is HTMLElement => s !== null);
    if (secciones.length === 0) return;
    const observador = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) if (entrada.isIntersecting) setActual(`#${entrada.target.id}`);
      },
      { rootMargin: '-35% 0px -60% 0px' },
    );
    secciones.forEach((s) => observador.observe(s));
    return () => observador.disconnect();
  }, [anclas]);

  // ¿Hay algo de compra en pantalla? Entonces el botón fijo sobra.
  useEffect(() => {
    const visibles = new Set<string>();
    const elementos = compra.map((id) => document.getElementById(id)).filter((s): s is HTMLElement => s !== null);
    if (elementos.length === 0) return;
    const observador = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (entrada.isIntersecting) visibles.add(entrada.target.id);
        else visibles.delete(entrada.target.id);
      }
      setCompraVisible(visibles.size > 0);
    });
    elementos.forEach((s) => observador.observe(s));
    return () => observador.disconnect();
  }, [compra]);

  // Con las pastillas a la vista, los saltos a una sección dejan su alto libre arriba.
  useEffect(() => {
    const raiz = document.documentElement;
    raiz.style.setProperty('--secciones-alto', trasHeroe ? '3.5rem' : '0px');
    return () => raiz.style.setProperty('--secciones-alto', '0px');
  }, [trasHeroe]);

  // La pastilla de la sección actual entra a la vista dentro del carril (sin mover la página). `offsetLeft` se mide
  // contra el carril (es `relative`).
  useEffect(() => {
    const lista = carril.current;
    const li = lista?.querySelector<HTMLElement>('[aria-current="location"]')?.parentElement;
    if (!lista || !li) return;
    const margen = parseFloat(getComputedStyle(lista).paddingLeft) || 16;
    if (li.offsetLeft - margen < lista.scrollLeft || li.offsetLeft + li.offsetWidth + margen > lista.scrollLeft + lista.clientWidth) {
      lista.scrollTo({ left: Math.max(0, li.offsetLeft - margen), behavior: sinMovimiento ? 'auto' : 'smooth' });
    }
  }, [actual, sinMovimiento]);

  const conBoton = trasHeroe && !compraVisible;

  return (
    <>
      <div ref={marcador} aria-hidden="true" className="h-0" />
      {anclas.length > 1 && (
        <nav
          aria-label={etiqueta}
          data-visible={trasHeroe}
          // Desde 1280 px la barra de arriba ya enseña estas mismas secciones como enlaces: repetirlas debajo era
          // la misma navegación dos veces (dueño, 2026-11-17). Las pastillas son del teléfono y la tablet.
          className="aparece-desde-arriba pointer-events-none fixed inset-x-0 top-[calc(var(--nav-alto)+0.5rem)] z-30 data-[visible=true]:pointer-events-auto xl:hidden"
        >
          <ul
            ref={carril}
            onScroll={medirBordes}
            data-izquierda={bordes.izquierda}
            data-derecha={bordes.derecha}
            className="carril-pastillas relative flex gap-2 overflow-x-auto px-[1.05rem] [scrollbar-width:none] sm:px-[2.1rem] lg:px-[2.8rem] [&::-webkit-scrollbar]:hidden"
          >
            {anclas.map((a) => (
              <li key={a.ancla} className="shrink-0">
                <Link
                  href={a.ancla}
                  aria-current={actual === a.ancla ? 'location' : undefined}
                  tabIndex={trasHeroe ? undefined : -1}
                  className={cn(
                    'inline-flex min-h-11 items-center whitespace-nowrap rounded-full px-5 texto-pequeno font-semibold transition-[color,background-color,transform] duration-200 active:scale-[0.97] motion-reduce:transform-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                    actual === a.ancla ? 'bg-tinta text-hero-ink' : 'bg-superficie text-foreground',
                  )}
                >
                  {a.etiqueta}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
      <div
        data-visible={conBoton}
        className="aparece-desde-abajo pointer-events-none fixed inset-x-0 bottom-0 z-30 px-[1.05rem] pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:flex sm:justify-end sm:px-[2.1rem] sm:pb-6 lg:px-[2.8rem] lg:pb-8"
      >
        <Link
          href={reservar.ancla}
          tabIndex={conBoton ? undefined : -1}
          aria-hidden={!conBoton}
          className={cn(botonClases({ variante: 'campana' }), 'flex min-h-14 w-full items-center justify-between gap-3 rounded-full px-6 sm:w-auto sm:gap-8 sm:pl-7 sm:pr-6 sm:shadow-n2 [@media(hover:hover)]:hover:-translate-y-0.5 transition-transform motion-reduce:transform-none', conBoton && 'pointer-events-auto')}
        >
          <span className="flex flex-col items-start leading-tight">
            {reservar.desde && <span className="texto-pequeno font-normal tabular-nums">{reservar.desde}</span>}
            <span className="font-semibold">{reservar.texto}</span>
          </span>
          <ArrowRight size={20} weight="bold" aria-hidden="true" />
        </Link>
      </div>
    </>
  );
}
