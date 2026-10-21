'use client';

import { useState } from 'react';
import { columnasDeMosaico } from '@/lib/mosaico';
import { Button } from '@/components/ui/button';
import { FotoFundido } from '@/components/ui/foto-fundido';
import { VisorGaleria, type FotoVisor } from '@/components/ui/visor-galeria';
import { cn } from '@/components/ui/cn';

type Props = {
  fotos: FotoVisor[];
  textosVisor: { cerrar: string; anterior: string; siguiente: string; contador: string };
};

// Clases completas para que Tailwind las vea: columnas de 12 en escritorio.
const COLUMNAS: Record<number, string> = {
  3: 'md:col-span-3',
  4: 'md:col-span-4',
  5: 'md:col-span-5',
  7: 'md:col-span-7',
  12: 'md:col-span-12',
};

/**
 * Las fotos de los viajes en mosaico (F10): en escritorio, filas de 12 columnas con 2, 3 o 4 fotos; en el
 * teléfono, una foto ancha y dos cuadradas, repetido. Cada foto abre el visor a pantalla completa.
 */
export function GaleriaMosaico({ fotos, textosVisor }: Props) {
  const [abierta, setAbierta] = useState<number | null>(null);
  const columnas = columnasDeMosaico(fotos.length);

  return (
    <>
      <div className="mt-10 grid grid-cols-2 gap-2 md:grid-cols-12 md:gap-2.5">
        {fotos.map((foto, i) => (
          <Button
            key={foto.src}
            variante="libre"
            aria-haspopup="dialog"
            onClick={() => setAbierta(i)}
            className={cn(
              'group relative block cursor-zoom-in overflow-hidden bg-cafe-bruma focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              i % 3 === 0 ? 'col-span-2 aspect-[4/3]' : 'aspect-square',
              'md:aspect-auto md:h-[clamp(11rem,19vw,17rem)]',
              COLUMNAS[columnas[i]],
            )}
          >
            <FotoFundido
              src={foto.src}
              alt={foto.alt}
              fill
              loading={i < 2 ? 'eager' : 'lazy'}
              sizes="(min-width: 768px) 60vw, 100vw"
              className="object-cover transition-[opacity,transform] duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-opacity [@media(hover:hover)]:group-hover:scale-105"
            />
          </Button>
        ))}
      </div>
      <VisorGaleria fotos={fotos} indice={abierta} onCambiar={setAbierta} textos={textosVisor} />
    </>
  );
}
