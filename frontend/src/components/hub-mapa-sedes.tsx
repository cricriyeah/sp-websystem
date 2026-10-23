'use client';
import { botonClases } from '@/components/ui/variantes';
import { useRef, useState } from 'react';
import Image from 'next/image';
import { LazyMotion, domMax, m, useMotionValue, useReducedMotion } from 'framer-motion';
import { ArrowCounterClockwise, Minus, Plus } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { Button } from '@/components/ui/button';

// Town centres, not departure docks. Same projection as generate-baja-map.cjs.
const COORDENADAS: Record<string, [number, number]> = {
  'la-paz': [-110.3128, 24.1426], 'la-ventana': [-109.989, 24.048], 'puerto-chale': [-111.5532, 24.4235],
};
const project = ([lon, lat]: [number, number]) => ({
  left: `${(330 + (lon + 117.5) * 48 * Math.cos(28 * Math.PI / 180)) / 10}%`,
  top: `${(28 + (33 - lat) * 48) / 5.6}%`,
});

/** Lo que muestra el panel de una sede: dónde queda y qué es. Lo que se reserva y el precio están en su cortina. */
export type SedeMapa = {
  slug: string;
  nombre: string;
  /** El ancla de su cortina en el hub (`#sede-<slug>`). */
  href: string;
  subtitulo: string;
  /** Foto genérica de Baja, solo del hub (nunca de las cortinas ni de la página de la sede). */
  foto: { src: string; alt: string } | null;
};
export type CopyMapa = Pick<Dictionary['hub'], 'mapAria' | 'pacificOcean' | 'seaOfCortez' | 'zoomIn' | 'zoomOut' | 'resetMap' | 'dragMap'> & {
  verSede: string;
};

// La sede que se ve abierta al llegar (dueño, 2026-10-22).
const SEDE_INICIAL = 'la-paz';

export function HubMapaSedes({ sedes, copy }: {
  sedes: SedeMapa[]; copy: CopyMapa;
}) {
  // Siempre hay una sede abierta: La Paz al llegar; las píldoras cambian cuál.
  const [abiertoSlug, setAbiertoSlug] = useState(() => (sedes.some((s) => s.slug === SEDE_INICIAL) ? SEDE_INICIAL : sedes[0]?.slug));
  const [zoom, setZoom] = useState(1);
  const x = useMotionValue(0), y = useMotionValue(0);
  const arrastrando = useRef(false);
  const sinMovimiento = useReducedMotion();
  const sede = sedes.find(s => s.slug === abiertoSlug);
  const contra = 1 / zoom;
  function reset() { setZoom(1); x.set(0); y.set(0); }
  function abrir(s: SedeMapa) { setAbiertoSlug(s.slug); }
  function cambiarZoom(delta: number) { setZoom(z => Math.min(4, Math.max(1, z + delta))); }
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <div className="flex flex-wrap gap-2">
          {sedes.map(s => <Button key={s.slug} variante="chip" onClick={() => abrir(s)} aria-pressed={abiertoSlug === s.slug} className={abiertoSlug === s.slug ? 'border-tinta bg-tinta text-white' : 'border-tinta bg-superficie text-foreground hover:bg-cafe-claro'}>{s.nombre}</Button>)}
        </div>
        <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer" className="text-sm text-foreground underline underline-offset-4">Natural Earth</a>
      </div>
      <div aria-live="polite" className="mb-4">
        {sede && (
          // Al cambiar de sede la tarjeta se abre de izquierda a derecha; con «reducir movimiento», solo aparece.
          <m.div
            key={sede.slug}
            initial={sinMovimiento ? { opacity: 0 } : { clipPath: 'inset(0 100% 0 0)' }}
            animate={sinMovimiento ? { opacity: 1 } : { clipPath: 'inset(0 0% 0 0)' }}
            transition={{ duration: sinMovimiento ? 0.15 : 0.6, ease: [0.2, 0, 0, 1] }}
            className="relative grid bg-tinta text-hero-ink lg:grid-cols-12"
          >
            <div className="relative min-h-[20rem] lg:col-span-5">
              {sede.foto && <Image src={sede.foto.src} alt={sede.foto.alt} fill sizes="40vw" className="object-cover" />}
            </div>
            <div className="flex flex-col gap-5 p-8 lg:col-span-7 lg:p-10">
              <p className="texto-seccion">{sede.nombre}</p>
              {sede.subtitulo && <p className="max-w-[52ch] text-lg leading-snug">{sede.subtitulo}</p>}
              <a href={sede.href} className={`mt-auto self-start ${botonClases({ variante: 'campana-claro' })}`}>
                {copy.verSede.replace('{sede}', sede.nombre)}
                <span aria-hidden="true">↓</span>
              </a>
            </div>
          </m.div>
        )}
      </div>
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
              {/* Puntos, etiquetas y nombres de los mares se contraescalan: el mapa se acerca, ellos no crecen. */}
              <span style={{ scale: contra }} className="pointer-events-none absolute left-[26%] top-[60%] origin-top-left texto-pie text-hero-ink">{copy.pacificOcean}</span>
              <span style={{ scale: contra }} className="pointer-events-none absolute left-[58%] top-[36%] origin-top-left texto-pie text-hero-ink">{copy.seaOfCortez}</span>
              {sedes.map(s => COORDENADAS[s.slug] && (
                <Button key={s.slug} variante="libre" aria-label={s.nombre} aria-pressed={abiertoSlug === s.slug}
                  onClick={() => { if (!arrastrando.current) abrir(s); }} style={{ ...project(COORDENADAS[s.slug]), scale: contra }}
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
    </div>
  );
}
