import type { EstadoCelda } from '@/lib/calendario-mes';
import type { ControlFecha } from '@/lib/control-fecha';
import { CeldaDia } from './celda-dia';
import type { TextosCalendario } from './textos';

const celda = (parcial: Partial<EstadoCelda>): EstadoCelda => ({
  base: 'disponible', marca: 'ninguna', hoy: false, inicioBanda: false, finBanda: false, ...parcial,
});

type Props = {
  control: ControlFecha;
  /** Hay dato de cupo para este control: solo entonces existe «Sin cupo». */
  conCupo: boolean;
  marcaHoy: boolean;
  textos: TextosCalendario['leyenda'];
};

/**
 * Solo los estados que pueden aparecer en este control, dibujados con la misma `CeldaDia` a
 * 24 px: color y forma, no solo color. En móvil en 2 columnas; desde 640 px en una fila.
 */
export function Leyenda({ control, conCupo, marcaHoy, textos }: Props) {
  const rango = control !== 'fecha_unica';
  const items: { clave: string; estado: EstadoCelda; texto: string; contorno?: boolean }[] = [
    { clave: 'disponible', estado: celda({}), texto: textos.disponible, contorno: true },
    ...(conCupo ? [{ clave: 'sin_cupo', estado: celda({ base: 'sin_cupo' }), texto: textos.sinCupo }] : []),
    { clave: 'seleccion', estado: celda({ marca: 'seleccion' }), texto: textos.seleccion },
    ...(rango ? [
      { clave: 'vista_previa', estado: celda({ marca: 'vista_previa', inicioBanda: true, finBanda: true }), texto: textos.vistaPrevia },
      { clave: 'rango', estado: celda({ marca: 'rango' }), texto: textos.rango },
    ] : []),
    ...(marcaHoy ? [{ clave: 'hoy', estado: celda({ hoy: true }), texto: textos.hoy }] : []),
  ];
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-2 texto-pequeno text-apagado sm:flex sm:flex-wrap">
      {items.map((item) => (
        <li key={item.clave} className="flex items-center gap-2">
          <CeldaDia numero="" estado={item.estado} tamano={24} contorno={item.contorno} className="w-6" />
          {item.texto}
        </li>
      ))}
    </ul>
  );
}
