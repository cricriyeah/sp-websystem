type Props = {
  /** 1 a 3; un valor mayor (pago 2 de 2 en cruza-empresa) se queda en el último segmento. */
  actual: number;
  /** Nombres de los tres pasos: viaje, datos, pago. */
  nombres: [string, string, string];
  /** «Paso {current} de {total}»: la plantilla del diccionario. */
  plantilla: string;
  className?: string;
};

/**
 * Tres segmentos sin números: el avance se lee de un vistazo y el nombre del paso queda visible.
 * Es una lista con `aria-current="step"` en el segmento actual, no un `progressbar`. El relleno
 * crece con `scaleX` desde la izquierda (nunca con `width`).
 */
export function LineaProgreso({ actual, nombres, plantilla, className }: Props) {
  const paso = Math.min(Math.max(actual, 1), 3);
  const texto = plantilla.replace('{current}', String(paso)).replace('{total}', '3');
  return (
    <div className={className}>
      <ol className="flex gap-2">
        {nombres.map((nombre, i) => {
          const numero = i + 1;
          return (
            <li key={nombre} aria-current={numero === paso ? 'step' : undefined} className="h-1 flex-1 overflow-hidden rounded-full bg-cafe-claro">
              <span
                aria-hidden
                className={`block h-full origin-left rounded-full bg-cafe transition-transform duration-[var(--duracion-media)] ease-[var(--curva-estandar)] motion-reduce:transition-none ${
                  numero <= paso ? 'scale-x-100' : 'scale-x-0'
                }`}
              />
            </li>
          );
        })}
      </ol>
      <p className="mt-2 texto-pequeno font-semibold text-foreground">{nombres[paso - 1]}</p>
      <p className="sr-only">{`${texto}: ${nombres[paso - 1]}`}</p>
    </div>
  );
}
