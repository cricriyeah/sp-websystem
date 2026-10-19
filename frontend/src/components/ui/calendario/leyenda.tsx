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
 * Solo lo que no se explica solo: la selección (o los extremos y los días del rango, con el
 * nombre de lo que se reserva), «Sin cupo» si este control lo sabe y «Hoy» si cae en el mes.
 * «Disponible» es lo normal y la vista previa se explica mientras ocurre. Cada muestra es la
 * misma `CeldaDia` a 24 px, siempre en círculo: color y forma.
 */
export function Leyenda({ control, conCupo, marcaHoy, textos }: Props) {
  const idaRegreso = control === 'ida_y_regreso';
  const items: { clave: string; estado: EstadoCelda; texto: string }[] = [
    ...(control === 'fecha_unica'
      ? [{ clave: 'seleccion', estado: celda({ marca: 'seleccion' }), texto: textos.seleccion }]
      : [
          { clave: 'extremos', estado: celda({ marca: 'extremo' }), texto: idaRegreso ? textos.extremosIdaRegreso : textos.extremosEstancia },
          { clave: 'rango', estado: celda({ marca: 'rango' }), texto: idaRegreso ? textos.diasViaje : textos.diasEstancia },
        ]),
    ...(conCupo ? [{ clave: 'sin_cupo', estado: celda({ base: 'sin_cupo' }), texto: textos.sinCupo }] : []),
    ...(marcaHoy ? [{ clave: 'hoy', estado: celda({ hoy: true }), texto: textos.hoy }] : []),
  ];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-2 texto-pequeno text-apagado">
      {items.map((item) => (
        <li key={item.clave} className="flex items-center gap-2">
          <CeldaDia numero="" estado={item.estado} tamano={24} className="w-6" />
          {item.texto}
        </li>
      ))}
    </ul>
  );
}
