import { TarjetaSedeHub, type VistaSedeHub } from '@/components/tarjeta-sede-hub';
import { cn } from '@/components/ui/cn';

type HubGridSedesProps = {
  sedes: VistaSedeHub[];
  textos: { region: string; desde: string; verSede: string };
};

/**
 * Las sedes en tarjetas: en móvil son el selector (el mapa es solo de escritorio). Una columna
 * en 360 px; dos en 768 px, y si son tres la tercera ocupa las dos para no dejar una celda
 * vacía; tres iguales y de la misma altura desde 1280 px.
 */
export function HubGridSedes({ sedes, textos }: HubGridSedesProps) {
  const tercera = sedes.length === 3 ? 2 : -1;
  return (
    <div className="grid gap-4 md:grid-cols-2 md:gap-6 xl:auto-rows-fr xl:grid-cols-3">
      {sedes.map((sede, i) => (
        <TarjetaSedeHub
          key={sede.slug}
          vista={sede}
          textos={textos}
          horizontalEnMd={i === tercera}
          className={cn(i === tercera && 'md:col-span-2 xl:col-span-1')}
        />
      ))}
    </div>
  );
}
