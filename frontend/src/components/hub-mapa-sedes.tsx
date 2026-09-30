'use client';
import { useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { motion, useMotionValue } from 'motion/react';
import { ArrowCounterClockwise, Minus, Plus, X } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';
import { hrefSede } from '@/lib/routes';

// Town centres, not departure docks. Same projection as generate-baja-map.cjs.
const COORDENADAS: Record<string, [number, number]> = {
  'la-paz': [-110.3128, 24.1426], 'la-ventana': [-109.989, 24.048], 'puerto-chale': [-111.5532, 24.4235],
};
const project = ([lon, lat]: [number, number]) => ({
  left: `${(330 + (lon + 117.5) * 48 * Math.cos(28 * Math.PI / 180)) / 10}%`,
  top: `${(28 + (33 - lat) * 48) / 5.6}%`,
});

export function HubMapaSedes({ lang, sedes, copy }: {
  lang: Locale; sedes: SedeContenido[]; copy: Dictionary['hub'];
}) {
  const [abiertoSlug, setAbiertoSlug] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const x = useMotionValue(0), y = useMotionValue(0);
  const arrastrando = useRef(false);
  const sede = sedes.find(s => s.slug === abiertoSlug);
  function reset() { setZoom(1); x.set(0); y.set(0); }
  function cambiarZoom(delta: number) { setZoom(z => Math.min(4, Math.max(1, z + delta))); }
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="relative">
        <div role="region" tabIndex={0}
          aria-label={copy.mapAria}
          onKeyDown={event => {
            if (event.target !== event.currentTarget) return;
            const moves: Record<string, [number, number]> = { ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40] };
            if (moves[event.key]) {
              event.preventDefault();
              const [dx, dy] = moves[event.key];
              x.set(Math.max(-800, Math.min(800, x.get() + dx)));
              y.set(Math.max(-600, Math.min(600, y.get() + dy)));
            }
            if (event.key === '+' || event.key === '=') cambiarZoom(0.5);
            if (event.key === '-') cambiarZoom(-0.5);
            if (event.key === 'Home') reset();
          }}
          className="relative h-[420px] overflow-hidden outline-offset-[-3px] focus-visible:outline-2 focus-visible:outline-accent sm:h-[520px]">
          <motion.div drag dragMomentum={false} dragElastic={0.08}
            dragConstraints={{ left: -800, right: 800, top: -600, bottom: 600 }}
            onDragStart={() => { arrastrando.current = true; }}
            onPointerDown={() => { arrastrando.current = false; }}
            style={{ x, y, scale: zoom, touchAction: 'none' }}
            className="absolute inset-0 cursor-grab active:cursor-grabbing">
            <div className="absolute left-1/2 top-1/2 aspect-[1000/560] w-[800px] max-w-none -translate-x-1/2 -translate-y-1/2 sm:w-[920px]">
              <Image src="/ilustraciones/mapa-baja.svg" alt="" fill loading="eager" sizes="(min-width: 640px) 920px, 800px" draggable={false} className="pointer-events-none select-none" />
              <span className="pointer-events-none absolute left-[26%] top-[60%] text-[11px] tracking-widest text-muted">{copy.pacificOcean}</span>
              <span className="pointer-events-none absolute left-[58%] top-[36%] text-[11px] tracking-widest text-muted">{copy.seaOfCortez}</span>
              {sedes.map(s => COORDENADAS[s.slug] && (
                <button key={s.slug} type="button" aria-label={s.nombre} aria-pressed={abiertoSlug === s.slug}
                  onClick={() => { if (!arrastrando.current) setAbiertoSlug(s.slug); }} style={project(COORDENADAS[s.slug])}
                  className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-accent">
                  <span className={`h-3.5 w-3.5 rounded-full border-2 border-white bg-accent shadow-sm ${abiertoSlug === s.slug ? 'ring-4 ring-accent/25' : ''}`} />
                  <span className={`absolute whitespace-nowrap rounded bg-background/95 px-2 py-1 text-xs font-semibold text-foreground shadow-sm ${s.slug === 'puerto-chale' ? 'right-9 top-0' : s.slug === 'la-paz' ? 'bottom-9 left-4' : 'left-9 top-6'}`}>{s.nombre}</span>
                </button>
              ))}
            </div>
          </motion.div>
        </div>
        <div className="absolute right-4 top-4 flex flex-col overflow-hidden rounded-xl border border-border bg-background shadow-sm">
          {[
            { title: copy.zoomIn, icon: Plus, action: () => cambiarZoom(0.5), disabled: zoom === 4 },
            { title: copy.zoomOut, icon: Minus, action: () => cambiarZoom(-0.5), disabled: zoom === 1 },
            { title: copy.resetMap, icon: ArrowCounterClockwise, action: reset, disabled: false },
          ].map(({ title, icon: Icon, action, disabled }) => <button key={title} type="button" aria-label={title} title={title} onClick={action} disabled={disabled} className="flex h-11 w-11 items-center justify-center text-foreground hover:bg-surface disabled:opacity-30"><Icon size={19} /></button>)}
        </div>
        <span className="pointer-events-none absolute left-4 top-4 rounded bg-background/90 px-3 py-2 text-xs text-muted">{copy.dragMap}</span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-background px-5 py-3">
        <div className="flex flex-wrap gap-2">
          {sedes.map(s => <button key={s.slug} type="button" onClick={() => setAbiertoSlug(s.slug)} aria-pressed={abiertoSlug === s.slug} className={`rounded-full border px-4 py-2 text-sm transition-colors ${abiertoSlug === s.slug ? 'border-accent bg-accent text-white' : 'border-border text-foreground hover:border-accent'}`}>{s.nombre}</button>)}
        </div>
        <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer" className="text-xs text-muted underline underline-offset-4">Natural Earth</a>
      </div>
      {sede && <div aria-live="polite" className="flex flex-wrap items-center gap-4 border-t border-border bg-background p-5">
        <div className="min-w-0 flex-1"><p className="font-semibold">{sede.nombre}</p>{sede.empresaFundadoraNombre && <p className="text-sm text-muted">{copy.conLabel} {sede.empresaFundadoraNombre}</p>}</div>
        <Link href={hrefSede(lang, sede.slug)} className="rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white">{copy.verDestino}</Link>
        <button type="button" aria-label={copy.closeDestination} onClick={() => setAbiertoSlug(null)} className="flex h-11 w-11 items-center justify-center"><X size={20} /></button>
      </div>}
    </div>
  );
}
