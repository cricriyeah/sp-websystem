// frontend/src/components/selector-experiencia.tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { resolverChips, esInlineable } from '@/lib/selector-experiencia';
import { BookingBar } from '@/components/booking-bar';
import { ID_BARRA_PORTADA } from '@/components/sticky-booking-bar';

type SelectorExperienciaProps = {
  lang: Locale;
  sedeSlug: string;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  minDate: string;
  verTodoLabel: string;
  hrefVerTodo: string;
};

const EMPRESA_PESCA_LEGACY = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

export function SelectorExperiencia({
  lang,
  sedeSlug,
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  minDate,
  verTodoLabel,
  hrefVerTodo,
}: SelectorExperienciaProps) {
  const [inlineAbierto, setInlineAbierto] = useState(false);
  const chips = resolverChips(destacadas, paquetes, servicios);

  return (
    <div className="relative z-10 mt-6 flex flex-wrap items-center gap-3">
      {chips.map((chip) => {
        const inline = esInlineable(chip, sedeSlug, EMPRESA_PESCA_LEGACY);
        const href =
          chip.tipo === 'paquete'
            ? hrefPaquete(paquetes.find((p) => p.slug === chip.slug)!, lang, moneda)
            : hrefServicio(servicios.find((s) => s.slug === chip.slug && s.empresa_slug === chip.empresaSlug)!, lang, moneda);

        if (inline) {
          return (
            <button
              key={`${chip.tipo}-${chip.slug}`}
              type="button"
              onClick={() => setInlineAbierto(true)}
              className="rounded-full border border-accent bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
            >
              {chip.nombre}
            </button>
          );
        }

        return (
          <Link
            key={`${chip.tipo}-${chip.slug}`}
            href={href}
            className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            {chip.nombre}
          </Link>
        );
      })}

      <Link
        href={hrefVerTodo}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-foreground"
      >
        {verTodoLabel}
        <ArrowRight size={14} />
      </Link>

      {inlineAbierto && (
        // Unico punto de montaje de `BookingBar` en la pagina de sede (2026-09-16:
        // antes tambien vivia, siempre visible, dentro de `SedeHero` — quedaba
        // duplicado con este y el Paso 0 no gateaba nada). `ID_BARRA_PORTADA`
        // vive aqui para que `StickyBookingBar` lo siga vigilando sin cambios.
        <div id={ID_BARRA_PORTADA} className="mt-4 w-full">
          <BookingBar lang={lang} booking={booking} minDate={minDate} />
        </div>
      )}
    </div>
  );
}
