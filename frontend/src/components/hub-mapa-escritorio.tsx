'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { CopyMapa, SedeMapa } from '@/components/hub-mapa-sedes';
import { Skeleton } from '@/components/skeleton';

const ALTO = 'h-[560px]';

const HubMapaSedes = dynamic(() => import('@/components/hub-mapa-sedes').then((m) => m.HubMapaSedes), {
  ssr: false,
  loading: () => <Skeleton className={`${ALTO} w-full`} />,
});

/**
 * El mapa interactivo es ayuda secundaria de escritorio: solo desde 1024 px se descarga y se
 * monta. En móvil no se pide nada (las tarjetas son el selector). Mientras decide, el esqueleto
 * guarda el alto para que nada brinque.
 */
export function HubMapaEscritorio(props: { lang: Locale; sedes: SedeMapa[]; copy: CopyMapa }) {
  const [escritorio, setEscritorio] = useState<boolean | null>(null);

  useEffect(() => {
    const consulta = window.matchMedia('(min-width: 1024px)');
    const actualizar = () => setEscritorio(consulta.matches);
    actualizar();
    consulta.addEventListener('change', actualizar);
    return () => consulta.removeEventListener('change', actualizar);
  }, []);

  if (escritorio === false) return null;
  if (escritorio === null) return <Skeleton className={`${ALTO} w-full`} />;
  return <HubMapaSedes {...props} />;
}
