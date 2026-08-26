'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';

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
