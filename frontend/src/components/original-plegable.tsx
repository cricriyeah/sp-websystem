'use client';

import { useId, useState } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Despliegue } from '@/components/ui/despliegue';

type Props = {
  /** El texto tal cual lo escribió el cliente. */
  texto: string;
  idioma: 'es' | 'en';
  textos: { ver: string; ocultar: string };
};

/**
 * «Ver original» bajo una reseña traducida: abre el texto original con la misma curva de altura y opacidad que el
 * resto del sitio (`Despliegue`), así lo de abajo baja sin brincar. Con «reducir movimiento», solo opacidad.
 */
export function OriginalPlegable({ texto, idioma, textos }: Props) {
  const [abierto, setAbierto] = useState(false);
  const id = useId();

  return (
    <div>
      <Button variante="texto" className="-ml-3 font-semibold" aria-expanded={abierto} aria-controls={id} onClick={() => setAbierto((a) => !a)}>
        <span>{abierto ? textos.ocultar : textos.ver}</span>
        <CaretDown size={12} weight="bold" aria-hidden="true" className={`transition-transform duration-[var(--duracion-media)] ${abierto ? 'rotate-180' : ''}`} />
      </Button>
      <div id={id}>
        <Despliegue abierto={abierto}>
          <blockquote lang={idioma} className="pt-1 texto-cuerpo">
            <p>“{texto}”</p>
          </blockquote>
        </Despliegue>
      </div>
    </div>
  );
}
