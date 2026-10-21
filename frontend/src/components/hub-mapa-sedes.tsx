'use client';
import { botonClases } from '@/components/ui/variantes';
import { useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { LazyMotion, domMax, m, useMotionValue } from 'framer-motion';
import { ArrowCounterClockwise, Minus, Plus, X } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { hrefSede } from '@/lib/routes';
import { Button } from '@/components/ui/button';

// Town centres, not departure docks. Same projection as generate-baja-map.cjs.
const COORDENADAS: Record<string, [number, number]> = {
  'la-paz': [-110.3128, 24.1426], 'la-ventana': [-109.989, 24.048], 'puerto-chale': [-111.5532, 24.4235],
};
const project = ([lon, lat]: [number, number]) => ({
  left: `${(330 + (lon + 117.5) * 48 * Math.cos(28 * Math.PI / 180)) / 10}%`,
  top: `${(28 + (33 - lat) * 48) / 5.6}%`,
});

export type SedeMapa = { slug: string; nombre: string; empresaProtagonistaNombre?: string };
export type CopyMapa = Pick<Dictionary['hub'], 'mapAria' | 'pacificOcean' | 'seaOfCortez' | 'zoomIn' | 'zoomOut' | 'resetMap' | 'dragMap' | 'closeDestination' | 'conLabel' | 'verDestino'>;

export function HubMapaSedes({ lang, sedes, copy }: {
  lang: Locale; sedes: SedeMapa[]; copy: CopyMapa;
}) {
  const [abiertoSlug, setAbiertoSlug] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const x = useMotionValue(0), y = useMotionValue(0);
  const arrastrando = useRef(false);
  const sede = sedes.find(s => s.slug === abiertoSlug);
  function reset() { setZoom(1); x.set(0); y.set(0); }
  function cambiarZoom(delta: number) { setZoom(z => Math.min(4, Math.max(1, z + delta))); }
  return (
    <div>
      <div className="relative overflow-hidden bg-azul">
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
          {/* `drag` solo existe en domMax; el proveedor global trae domAnimation.
              Sin este anidado el mapa dejaria de arrastrarse sin lanzar error. */}
          <LazyMotion features={domMax} strict>
          <m.div drag dragMomentum={false} dragElastic={0.08}
            dragConstraints={{ left: -800, right: 800, top: -600, bottom: 600 }}
            onDragStart={() => { arrastrando.current = true; }}
            onPointerDown={() => { arrastrando.current = false; }}
            style={{ x, y, scale: zoom, touchAction: 'none' }}
            className="absolute inset-0 cursor-grab active:cursor-grabbing">
            <div className="absolute left-1/2 top-1/2 aspect-[1000/560] w-[800px] max-w-none -translate-x-1/2 -translate-y-1/2 sm:w-[920px]">
              <Image src="/ilustraciones/mapa-baja.svg" alt="" fill loading="eager" sizes="(min-width: 640px) 920px, 800px" draggable={false} className="pointer-events-none select-none" />
              <span className="pointer-events-none absolute left-[26%] top-[60%] texto-pie text-hero-ink">{copy.pacificOcean}</span>
              <span className="pointer-events-none absolute left-[58%] top-[36%] texto-pie text-hero-ink">{copy.seaOfCortez}</span>
              {sedes.map(s => COORDENADAS[s.slug] && (
                <Button key={s.slug} variante="libre" aria-label={s.nombre} aria-pressed={abiertoSlug === s.slug}
                  onClick={() => { if (!arrastrando.current) setAbiertoSlug(s.slug); }} style={project(COORDENADAS[s.slug])}
                  className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-accent">
                  <span className={`h-3.5 w-3.5 rounded-full border-2 border-white bg-tinta ${abiertoSlug === s.slug ? 'ring-4 ring-tinta/30' : ''}`} />
                  <span className={`absolute whitespace-nowrap bg-superficie px-2 py-1 text-sm font-semibold text-foreground ${s.slug === 'puerto-chale' ? 'right-9 top-0' : s.slug === 'la-paz' ? 'bottom-9 left-4' : 'left-9 top-6'}`}>{s.nombre}</span>
                </Button>
              ))}
            </div>
          </m.div>
          </LazyMotion>
        </div>
        <div className="absolute right-4 top-4 flex flex-col gap-2">
          {[
            { title: copy.zoomIn, icon: Plus, action: () => cambiarZoom(0.5), disabled: zoom === 4 },
            { title: copy.zoomOut, icon: Minus, action: () => cambiarZoom(-0.5), disabled: zoom === 1 },
            { title: copy.resetMap, icon: ArrowCounterClockwise, action: reset, disabled: false },
          ].map(({ title, icon: Icon, action, disabled }) => <Button key={title} variante="libre" aria-label={title} title={title} onClick={action} disabled={disabled} className="flex h-11 w-11 items-center justify-center rounded-full bg-tinta text-white transition-colors hover:bg-cafe disabled:bg-cafe-claro disabled:text-tinta"><Icon size={19} /></Button>)}
        </div>
        <span className="pointer-events-none absolute left-4 top-4 bg-superficie px-3 py-2 text-sm text-foreground">{copy.dragMap}</span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex flex-wrap gap-2">
          {sedes.map(s => <Button key={s.slug} variante="chip" onClick={() => setAbiertoSlug(s.slug)} aria-pressed={abiertoSlug === s.slug} className={abiertoSlug === s.slug ? 'border-tinta bg-tinta text-white' : 'border-tinta bg-superficie text-foreground hover:bg-cafe-claro'}>{s.nombre}</Button>)}
        </div>
        <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer" className="text-sm text-foreground underline underline-offset-4">Natural Earth</a>
      </div>
      {sede && <div aria-live="polite" className="flex flex-wrap items-center gap-4 bg-tinta p-5 text-hero-ink">
        <div className="min-w-0 flex-1"><p className="font-semibold">{sede.nombre}</p>{sede.empresaProtagonistaNombre && <p className="text-sm">{copy.conLabel} {sede.empresaProtagonistaNombre}</p>}</div>
        <Link href={hrefSede(lang, sede.slug)} className={botonClases({ variante: 'campana-claro' })}>{copy.verDestino}</Link>
        <Button variante="libre" aria-label={copy.closeDestination} onClick={() => setAbiertoSlug(null)} className="flex h-11 w-11 items-center justify-center rounded-full bg-white/15 transition-colors hover:bg-white/25"><X size={20} /></Button>
      </div>}
    </div>
  );
}
