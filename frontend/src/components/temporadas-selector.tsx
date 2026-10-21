'use client';

import { useState, useSyncExternalStore } from 'react';
import Image from 'next/image';
import type { SedeTemporadas } from '@/content/sedes-tipos';
import { temporadaDeMes } from '@/lib/temporada-actual';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';

const suscribirseAlMes = () => () => {};

type Props = {
  temporadas: SedeTemporadas;
  textos: { ahora: string };
};

/**
 * El calendario de especies (F10): un marco con la foto y la especie estrella de la temporada elegida y,
 * debajo de la especie, un botón por temporada. Arranca en la temporada del mes de hoy (marcada con «ahora») o, sin ella, en la fuerte. Las fotos de todas las temporadas están montadas y se funden entre sí: cambiar
 * de temporada no espera a que cargue una foto.
 */
export function TemporadasSelector({ temporadas, textos }: Props) {
  const { filas } = temporadas;
  const fuerte = Math.max(0, filas.findIndex((fila) => fila.fuerte));
  // El mes de hoy es del navegador: el servidor no lo sabe (-1) y el cliente lo lee al hidratar.
  const mes = useSyncExternalStore(suscribirseAlMes, () => new Date().getMonth(), () => -1);
  const hoy = temporadaDeMes(filas, mes);
  const [tocada, setTocada] = useState<number | null>(null);
  const elegida = tocada ?? (hoy >= 0 ? hoy : fuerte);

  const fila = filas[elegida];

  const botones = (
    <div>
      <p className="texto-etiqueta">{temporadas.etiquetaCalendario}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {filas.map((f, i) => (
          <Button
            key={f.periodo}
            variante={i === elegida ? 'campana' : 'campana-gris'}
            aria-pressed={i === elegida}
            onClick={() => setTocada(i)}
          >
            {f.periodo}
            {i === hoy && <span className="font-normal">{`· ${textos.ahora}`}</span>}
          </Button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="mt-10 grid items-center gap-8 md:grid-cols-2 lg:gap-20">
      <div className="relative aspect-[4/3] overflow-hidden bg-cafe-bruma md:aspect-[4/5]">
        {filas.map((f, i) => (
          <Image
            key={f.foto}
            src={f.foto}
            alt={i === elegida ? f.estrella : ''}
            fill
            loading={i === fuerte ? 'eager' : 'lazy'}
            sizes="(min-width: 768px) 50vw, 100vw"
            className={cn(
              'object-cover transition-[opacity,transform] duration-[600ms] ease-[var(--curva-estandar)] motion-reduce:transition-opacity',
              i === elegida ? 'opacity-100' : 'scale-105 opacity-0',
            )}
          />
        ))}
      </div>
      <div className="flex flex-col gap-10">
        <div aria-live="polite">
          <p className="texto-grande">{fila.estrella}</p>
          <p className="mt-3 text-xl font-semibold">
            {fila.periodo}
            {fila.fuerte && <span className="font-normal">{` · ${temporadas.etiquetaFuerte}`}</span>}
          </p>
          {fila.otras && (
            <p className="mt-6 max-w-[46ch] font-semibold">
              {temporadas.etiquetaOtras}: <span className="font-normal">{fila.otras}</span>
            </p>
          )}
        </div>
        {botones}
      </div>
    </div>
  );
}
