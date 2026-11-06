'use client';

import { useSyncExternalStore } from 'react';
import Link from 'next/link';
import type { Locale } from '@/app/[lang]/dictionaries';
import { botonClases } from '@/components/ui/variantes';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { ANCLA_DE, ANCLA_HUB } from '@/lib/secciones-sede';
import { leerSoloSedeCliente } from '@/lib/solo-sede';

// La cookie del modo no cambia con la página abierta: no hace falta suscribirse (igual que `SiteHeader`).
const sinSuscripcion = () => () => {};

/**
 * «Ver qué reservar» del pie en una página sin sede (privacidad, deslinde). Lleva a las sedes del
 * hub; en modo «solo sede» (lib/solo-sede.ts), a la sección de reservar de la sede del modo. El
 * servidor no lee la cookie (las páginas siguen estáticas): pinta el del hub y el navegador lo
 * corrige al hidratar. Sin esto, el proxy mandaba `/es#sedes` al inicio de la sede, sin la sección.
 */
export function BotonReservarPie({ lang, label }: { lang: Locale; label: string }) {
  const soloSede = useSyncExternalStore(sinSuscripcion, leerSoloSedeCliente, () => null);
  const href = soloSede ? hrefSede(lang, soloSede, ANCLA_DE.reservar) : hrefInicio(lang, ANCLA_HUB.sedes);
  return (
    <Link href={href} className={botonClases({ variante: 'campana-claro' })}>
      {label}
    </Link>
  );
}
