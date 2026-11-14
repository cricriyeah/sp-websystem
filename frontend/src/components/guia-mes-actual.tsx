'use client';

import { useSyncExternalStore } from 'react';

const MESES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
// El mes no cambia mientras la página está abierta: no hay a qué suscribirse.
const sinSuscripcion = () => () => {};

/**
 * La marca «Ahora» sobre la columna del mes de hoy, en la tira de doce del calendario de una guía. El mes se lee en el
 * navegador (como en las temporadas de la sede): la página es estática y en el servidor diría el mes en que se generó.
 * Antes de hidratar no pinta marca. Decorativa: quien usa lector de pantalla oye cada fila como una frase.
 */
export function MarcaMesActual({ etiqueta, className }: { etiqueta: string; className: string }) {
  const mes = useSyncExternalStore(sinSuscripcion, () => new Date().getMonth(), () => -1);
  return (
    <div className={className}>
      {MESES.map((i) => (
        <span key={i} className="flex justify-center">
          {i === mes && (
            <span className="whitespace-nowrap rounded-full bg-tinta px-2.5 py-1 texto-pequeno font-semibold leading-none text-white">
              {etiqueta}
            </span>
          )}
        </span>
      ))}
    </div>
  );
}
