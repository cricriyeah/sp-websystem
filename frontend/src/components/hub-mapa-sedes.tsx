'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { MapPin, X } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';

type HubMapaSedesProps = {
  lang: Locale;
  sedes: SedeContenido[];
  verDestinoLabel: string;
  conLabel: string;
};

/**
 * Posiciones ilustradas del pin dentro del SVG (porcentaje del contenedor),
 * no coordenadas geograficas reales (spec §2, §5.2). Agregar una sede nueva
 * = agregar su entrada aqui + en `content/sedes-indice.ts`, sin tocar el layout.
 */
const POSICION_PIN: Record<string, { top: string; left: string }> = {
  'la-paz': { top: '38%', left: '52%' },
  'los-cabos': { top: '82%', left: '58%' },
};

export function HubMapaSedes({ lang, sedes, verDestinoLabel, conLabel }: HubMapaSedesProps) {
  const [abiertoSlug, setAbiertoSlug] = useState<string | null>(null);
  const sedeAbierta = sedes.find((s) => s.slug === abiertoSlug) ?? null;

  return (
    <div className="relative mx-auto max-w-3xl">
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-3xl border border-border bg-surface">
        <Image
          src="/ilustraciones/mapa-baja.svg"
          alt="Ilustración de la península de Baja California Sur"
          fill
          className="object-contain p-6"
        />

        {sedes.map((sede) => {
          const pos = POSICION_PIN[sede.slug];
          if (!pos) return null;
          return (
            <button
              key={sede.slug}
              type="button"
              onClick={() => setAbiertoSlug(sede.slug === abiertoSlug ? null : sede.slug)}
              aria-label={sede.negocio?.nombre ?? sede.empresaFundadoraNombre}
              className="absolute flex h-9 w-9 -translate-x-1/2 -translate-y-full items-center justify-center rounded-full bg-accent text-white shadow-lg transition-transform hover:scale-110"
              style={{ top: pos.top, left: pos.left }}
            >
              <MapPin size={20} weight="fill" />
            </button>
          );
        })}
      </div>

      {sedeAbierta && (
        <div className="absolute inset-x-6 bottom-6 z-10 flex items-center gap-4 rounded-2xl border border-border bg-background p-4 shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-surface">
            {sedeAbierta.hero.imagen && (
              <Image src={sedeAbierta.hero.imagen} alt="" fill className="object-cover" />
            )}
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">
              {sedeAbierta.negocio?.nombre ?? sedeAbierta.empresaFundadoraNombre}
            </p>
            <p className="text-xs text-muted">
              {conLabel} {sedeAbierta.empresaFundadoraNombre}
            </p>
          </div>
          <Link
            href={`/${lang}/sede/${sedeAbierta.slug}`}
            className="shrink-0 rounded-full bg-accent px-4 py-2 text-xs font-semibold text-white"
          >
            {verDestinoLabel}
          </Link>
          <button
            type="button"
            onClick={() => setAbiertoSlug(null)}
            aria-label="Cerrar"
            className="shrink-0 text-muted hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
