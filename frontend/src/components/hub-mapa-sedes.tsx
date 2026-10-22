'use client';
import { botonClases } from '@/components/ui/variantes';
import { useRef, useState } from 'react';
import { Despliegue } from '@/components/ui/despliegue';
import { DURACION } from '@/lib/movimiento';
import Image from 'next/image';
import Link from 'next/link';
import { LazyMotion, domMax, m, useMotionValue } from 'framer-motion';
import { ArrowCounterClockwise, Minus, Plus, X } from '@phosphor-icons/react';
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

/** Lo que muestra el panel de una sede: lo mismo que su cortina (empresas, tipos, «desde») más su frase y una foto del hub. */
export type SedeMapa = {
  slug: string;
  nombre: string;
  href: string;
  empresas: string | null;
  subtitulo: string;
  tipos: string;
  desde: { monto: string; aprox?: string; base: string } | null;
  /** Foto genérica de Baja, solo del hub (nunca de las cortinas ni de la página de la sede). */
  foto: { src: string; alt: string } | null;
};
export type CopyMapa = Pick<Dictionary['hub'], 'mapAria' | 'pacificOcean' | 'seaOfCortez' | 'zoomIn' | 'zoomOut' | 'resetMap' | 'dragMap' | 'closeDestination'> & {
  desde: string;
  verSede: string;
};

// Después de `Despliegue` (duracion-media, 250 ms) el panel ya tiene su alto final.
const MS_DESPLIEGUE = DURACION.media * 1000 + 50;

export function HubMapaSedes({ sedes, copy }: {
  sedes: SedeMapa[]; copy: CopyMapa;
}) {
  const [abiertoSlug, setAbiertoSlug] = useState<string | null>(null);
  // La última sede abierta: el panel la sigue mostrando mientras se pliega.
  const [mostrada, setMostrada] = useState<SedeMapa | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const x = useMotionValue(0), y = useMotionValue(0);
  const arrastrando = useRef(false);
  const sede = sedes.find(s => s.slug === abiertoSlug);
  function reset() { setZoom(1); x.set(0); y.set(0); }
  /** Abre el panel y, si se desplegó fuera de la pantalla, lo trae a la vista (sin animación con «reducir movimiento»). */
  function abrir(s: SedeMapa) {
    setAbiertoSlug(s.slug);
    setMostrada(s);
    window.setTimeout(() => {
      const el = panel.current;
      if (!el || el.getBoundingClientRect().bottom <= window.innerHeight) return;
      const reducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ block: 'end', behavior: reducido ? 'auto' : 'smooth' });
    }, MS_DESPLIEGUE);
  }
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
                  onClick={() => { if (!arrastrando.current) abrir(s); }} style={project(COORDENADAS[s.slug])}
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
          {sedes.map(s => <Button key={s.slug} variante="chip" onClick={() => abrir(s)} aria-pressed={abiertoSlug === s.slug} className={abiertoSlug === s.slug ? 'border-tinta bg-tinta text-white' : 'border-tinta bg-superficie text-foreground hover:bg-cafe-claro'}>{s.nombre}</Button>)}
        </div>
        <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer" className="text-sm text-foreground underline underline-offset-4">Natural Earth</a>
      </div>
      <div ref={panel} aria-live="polite">
        <Despliegue abierto={Boolean(sede)}>
          {mostrada && (
            <div className="relative grid bg-tinta text-hero-ink lg:grid-cols-12">
              <div className="relative min-h-[20rem] lg:col-span-5">
                {mostrada.foto && <Image src={mostrada.foto.src} alt={mostrada.foto.alt} fill sizes="40vw" className="object-cover" />}
              </div>
              <div className="flex flex-col gap-5 p-8 pr-20 lg:col-span-7 lg:p-10 lg:pr-20">
                <div>
                  <p className="texto-seccion">{mostrada.nombre}</p>
                  {mostrada.empresas && <p className="mt-1 texto-cuerpo">{mostrada.empresas}</p>}
                </div>
                {mostrada.subtitulo && <p className="max-w-[52ch] texto-cuerpo">{mostrada.subtitulo}</p>}
                {mostrada.tipos && <p className="font-semibold">{mostrada.tipos}</p>}
                <div className="mt-auto flex flex-wrap items-end justify-between gap-4 pt-2">
                  {mostrada.desde && (
                    <p className="tabular-nums">
                      <span className="block texto-pequeno">{copy.desde}</span>
                      <span className="block text-2xl font-bold leading-tight">{mostrada.desde.monto}</span>
                      <span className="block texto-pequeno">
                        {mostrada.desde.aprox && `${mostrada.desde.aprox} · `}
                        {mostrada.desde.base}
                      </span>
                    </p>
                  )}
                  <Link href={mostrada.href} className={botonClases({ variante: 'campana-claro' })}>
                    {copy.verSede.replace('{sede}', mostrada.nombre)}
                    <span aria-hidden="true">→</span>
                  </Link>
                </div>
              </div>
              <Button variante="libre" aria-label={copy.closeDestination} onClick={() => setAbiertoSlug(null)} className="absolute right-4 top-4 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 transition-colors hover:bg-white/25"><X size={20} /></Button>
            </div>
          )}
        </Despliegue>
      </div>
    </div>
  );
}
