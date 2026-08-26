'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { getMinBookableDate, parseBookingQuery } from '@/lib/dates';

/** Nunca corre en el servidor: solo se llama dentro de un efecto. */
function precargaReserva() {
  const params = new URLSearchParams(window.location.search);
  return parseBookingQuery((key) => params.get(key) ?? undefined, getMinBookableDate());
}

export type EstadoReserva = {
  people: number | null;
  day: string | null;
  time: string | null;
  setPeople: (n: number | null) => void;
  setDay: (d: string | null) => void;
  setTime: (t: string | null) => void;
};

const ContextoReserva = createContext<EstadoReserva | null>(null);

/**
 * Las respuestas de la barra de reserva, compartidas entre las dos barras.
 *
 * En la portada hay una barra montada sobre la foto y otra pegada abajo que
 * aparece al bajar. Son dos instancias del mismo componente, y con el estado
 * dentro de cada una el cliente podia contestar "somos 4, el sabado" arriba,
 * seguir leyendo, y encontrarse la barra de abajo en blanco. Contestar dos
 * veces lo mismo es la clase de friccion que hace que la gente escriba por
 * WhatsApp en vez de reservar.
 *
 * Lo que **no** se comparte son los contadores que piden abrir cada panel: eso
 * es comportamiento de una barra concreta, y abrir el calendario en la barra de
 * arriba porque alguien toco la de abajo no tendria ningun sentido.
 */
export function ProveedorReserva({ children }: { children: ReactNode }) {
  const [people, setPeople] = useState<number | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const [time, setTime] = useState<string | null>(null);

  // Precarga con lo que el cliente ya habia contestado si vuelve del checkout
  // (ver el enlace "volver" en checkout-view.tsx). Va en un efecto, no en el
  // estado inicial: `window.location.search` no existe en el servidor, y
  // leerlo ahi produciria un primer pintado del cliente distinto del HTML ya
  // enviado (la pagina sigue pre-renderizada estatica). Contestar un instante
  // despues de montar es el precio de que la portada siga siendo estatica para
  // todo el mundo — mismo razonamiento que en `ref-capture.tsx` con `?ref=`.
  /* eslint-disable react-hooks/set-state-in-effect -- precarga unica desde una
     fuente que no existe en el servidor; no hay forma de calcularla durante
     el render sin romper la hidratacion. */
  useEffect(() => {
    const precarga = precargaReserva();
    if (precarga.people !== undefined) setPeople(precarga.people);
    if (precarga.day !== undefined) setDay(precarga.day);
    if (precarga.time !== undefined) setTime(precarga.time);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  return (
    <ContextoReserva.Provider value={{ people, day, time, setPeople, setDay, setTime }}>
      {children}
    </ContextoReserva.Provider>
  );
}

/**
 * Estado propio para una barra que vive fuera del proveedor.
 *
 * Existe para que `BookingBar` siga funcionando suelta, sin obligar a envolver
 * media aplicacion. Los dos hooks se llaman siempre —el del contexto y este— y
 * la barra usa el compartido si lo hay: llamarlos condicionalmente romperia el
 * orden de hooks entre renders.
 */
export function useEstadoReserva(): EstadoReserva {
  const compartido = useContext(ContextoReserva);

  const [people, setPeople] = useState<number | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const [time, setTime] = useState<string | null>(null);

  return compartido ?? { people, day, time, setPeople, setDay, setTime };
}
