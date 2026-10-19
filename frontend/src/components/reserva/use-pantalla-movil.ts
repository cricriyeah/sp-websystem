'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { guardarBorrador, leerBorrador } from '@/lib/borrador-reserva';
import { conPantalla, decidirPantalla, pantallaDeQuery } from '@/lib/paso-url';
import {
  anterior,
  estaAntesDe,
  pantallaValida,
  siguiente,
  type Pantalla,
} from '@/lib/pantallas-checkout';

type Opciones = {
  pantallas: readonly Pantalla[];
  /** Solo en móvil, y cuando el borrador y la reserva recuperada ya se repusieron. */
  habilitado: boolean;
  /** Dónde arranca sin `?pantalla=` en la URL (p. ej. la primera del paso al que llegó el cliente). */
  inicial: string;
  /** Con un pago en curso, la primera pantalla a la que todavía se puede volver. */
  minima: string | null;
  /** Clave del borrador de la ruta: la pantalla más avanzada se guarda a su lado. */
  clave: string;
  /** La más avanzada que se puede ver ahora (p. ej. «Cómo pagas» mientras no exista el pago). */
  tope?: string | null;
};

export type PantallaMovil = {
  pantalla: Pantalla;
  /** La más avanzada a la que llegó el cliente. */
  alcanzada: string;
  /** Pasa a la siguiente pantalla; la validación es de quien llama. */
  avanzar: () => void;
  /** Vuelve a la anterior; `false` en la primera (la flecha sale al origen). */
  retroceder: () => boolean;
  /** Salta a una pantalla ya alcanzada (p. ej. la del campo con error). */
  irA: (id: string) => void;
};

const masAvanzada = (pantallas: readonly Pantalla[], a: string, b: string) =>
  estaAntesDe(pantallas, a, b) ? b : a;

const hastaElTope = (pantallas: readonly Pantalla[], tope: string | null, id: string) =>
  tope && estaAntesDe(pantallas, tope, id) ? tope : id;

/**
 * Asistente móvil: una pantalla a la vez, cada una es una entrada de historial
 * (`?paso=…&pantalla=…`, con `pushState`), así que Atrás del navegador y la flecha hacen lo
 * mismo. Ir y venir no pierde nada: las respuestas viven en el estado de la ruta y en su
 * borrador; aquí solo se guarda en qué pantalla va el cliente y hasta cuál llegó.
 */
export function usePantallaMovil({ pantallas, habilitado, inicial, minima, clave, tope = null }: Opciones): PantallaMovil {
  const urlId = pantallaDeQuery(useSearchParams().get('pantalla'));
  const claveAlcanzada = `${clave}:pantalla`;
  const [actualCrudo, setActual] = useState<string>(inicial);
  const [alcanzadaCruda, setAlcanzada] = useState<string>(inicial);
  // La ruta puede cambiar sus pantallas (un servicio sin extras, un paquete sin traslado):
  // lo guardado se lee siempre contra la lista vigente.
  const limitar = (id: string) => hastaElTope(pantallas, tope, id);
  const actual = limitar(pantallaValida(pantallas, actualCrudo));
  const alcanzada = limitar(masAvanzada(pantallas, pantallaValida(pantallas, alcanzadaCruda), actual));
  // Lo último que el hook vio o escribió en la URL: distingue Atrás de un avance propio.
  const ultimo = useRef<string | null | undefined>(undefined);

  // Arranque y URL → estado (recarga, Atrás, Adelante).
  useEffect(() => {
    if (!habilitado) return;
    const primera = ultimo.current === undefined;
    if (!primera && ultimo.current === urlId) return;
    let hasta = alcanzada;
    if (primera) {
      const guardada = leerBorrador<string>(claveAlcanzada);
      hasta = hastaElTope(pantallas, tope, masAvanzada(pantallas, pantallaValida(pantallas, guardada), pantallaValida(pantallas, inicial)));
      setAlcanzada(hasta);
    }
    const decision = decidirPantalla(urlId, pantallas, hasta, minima);
    const destino = decision.tipo === 'mostrar' ? decision.id
      : decision.tipo === 'redirigir' ? decision.a
      : pantallaValida(pantallas, inicial);
    ultimo.current = destino;
    setActual(destino);
    // Alinear la URL sin sumar entrada: de otro modo Atrás se quedaría en la misma pantalla.
    if (urlId !== destino) window.history.replaceState(null, '', conPantalla(window.location.search, pantallas, destino));
  }, [habilitado, urlId, pantallas, alcanzada, minima, inicial, claveAlcanzada, tope]);

  useEffect(() => {
    if (habilitado) guardarBorrador(claveAlcanzada, alcanzada);
  }, [habilitado, claveAlcanzada, alcanzada]);

  const irA = useCallback((id: string) => {
    if (id === actual) return;
    ultimo.current = id;
    setActual(id);
    setAlcanzada((previa) => masAvanzada(pantallas, pantallaValida(pantallas, previa), id));
    window.history.pushState(null, '', conPantalla(window.location.search, pantallas, id));
  }, [actual, pantallas]);

  const avanzar = useCallback(() => {
    const proxima = siguiente(pantallas, actual);
    if (proxima) irA(proxima);
  }, [pantallas, actual, irA]);

  const retroceder = useCallback(() => {
    const previa = anterior(pantallas, actual);
    if (!previa || (minima && estaAntesDe(pantallas, previa, minima))) return false;
    irA(previa);
    return true;
  }, [pantallas, actual, minima, irA]);

  const pantalla = pantallas.find((x) => x.id === actual) ?? pantallas[0];
  return { pantalla, alcanzada, avanzar, retroceder, irA };
}
