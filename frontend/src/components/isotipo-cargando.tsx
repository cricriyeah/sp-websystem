import { cn } from '@/components/ui/cn';

const TRAZO = 'M82.89,25.77A17.56,17.56,0,0,0,71,25.56c-.37.12-.73.25-1.08.4a1.19,1.19,0,0,1-1.53-1.59,18.11,18.11,0,0,1,3.33-5.26,1.2,1.2,0,0,0-1.21-2h0A26.58,26.58,0,0,0,60,23.73a1.19,1.19,0,0,1-2-.92,18.28,18.28,0,0,1,1.21-5.45A1.19,1.19,0,0,0,57.32,16a40.76,40.76,0,0,0-14.81,24,36.66,36.66,0,0,1,1.63-25.83A1.21,1.21,0,0,0,44,12.84,18.05,18.05,0,0,1,39.74,1.28V1.22A1.19,1.19,0,0,0,37.62.46a18,18,0,0,0-3.87,11.32c0,.39,0,.78,0,1.16a1.19,1.19,0,0,1-2,1,18,18,0,0,1-3.92-4.83,1.18,1.18,0,0,0-2.23.56v0a27.06,27.06,0,0,0,2.93,12.15,1.2,1.2,0,0,1-1.49,1.67,17.91,17.91,0,0,1-4.76-2.85A1.19,1.19,0,0,0,20.49,22,40.58,40.58,0,0,0,38.05,43.38a35.38,35.38,0,0,1-17.89-6.16A37.16,37.16,0,0,1,15.1,33a1.17,1.17,0,0,0-1.23-.28,17.64,17.64,0,0,1-12.2.08l0,0A1.2,1.2,0,0,0,.18,34.56,17.84,17.84,0,0,0,9.39,42.1c.36.13.73.25,1.1.35a1.21,1.21,0,0,1,.23,2.21,17.75,17.75,0,0,1-5.83,2.07A1.2,1.2,0,0,0,4.65,49l0,0A26.37,26.37,0,0,0,17,50.43a1.19,1.19,0,0,1,1,2A17.91,17.91,0,0,1,13.76,56a1.2,1.2,0,0,0,.6,2.22,40,40,0,0,0,26.43-9.8A35.89,35.89,0,0,1,29.73,64.83a35.54,35.54,0,0,1-5.37,3.76,1.21,1.21,0,0,0-.61,1.13,18,18,0,0,1-3.29,11.86l0,0a1.2,1.2,0,0,0,1.27,1.88,17.8,17.8,0,0,0,9.71-6.86c.22-.32.44-.65.64-1a1.18,1.18,0,0,1,2.16.38,18.11,18.11,0,0,1,.36,6.23,1.19,1.19,0,0,0,2.13.87l0,0a27.15,27.15,0,0,0,4.69-11.57,1.18,1.18,0,0,1,2.17-.46,17.86,17.86,0,0,1,2.19,5.13,1.19,1.19,0,0,0,2.29,0,41,41,0,0,0-2-28.25A35.81,35.81,0,0,1,58,63.56a37.9,37.9,0,0,1,1.88,6.33,1.19,1.19,0,0,0,.86.93,17.8,17.8,0,0,1,10.16,6.83l0,0a1.19,1.19,0,0,0,2.16-.64A18.09,18.09,0,0,0,69.59,65.6c-.23-.31-.47-.62-.71-.91a1.2,1.2,0,0,1,1-2,17.61,17.61,0,0,1,6,1.58,1.2,1.2,0,0,0,1.48-1.78l0-.05a26.73,26.73,0,0,0-9.44-8.08,1.2,1.2,0,0,1,.24-2.23,17.68,17.68,0,0,1,5.5-.53,1.2,1.2,0,0,0,.74-2.18,39.9,39.9,0,0,0-27.05-6.84,35.27,35.27,0,0,1,18.2-6.51,35.64,35.64,0,0,1,6.54.15,1.19,1.19,0,0,0,1.14-.55,17.84,17.84,0,0,1,9.56-7.65l.07,0A1.21,1.21,0,0,0,82.89,25.77Z';

/**
 * El isotipo de la marca como indicador de carga. Primero solo el contorno, girando hacia la izquierda y
 * luego hacia la derecha (`.isotipo-oscila`); mientras tanto el relleno sube desde abajo y se frena cerca
 * del tope (`.isotipo-rellena`): el indicador no sabe cuánto falta, pero la página casi siempre llega
 * mientras se está llenando, y si tarda se queda lleno a ~92 %. Con «reducir movimiento» queda quieto y lleno.
 * Es decoración: el aviso para lectores de pantalla lo da `role="status"`.
 */
export function IsotipoCargando({ etiqueta, className }: { etiqueta: string; className?: string }) {
  return (
    <div role="status" className={cn('inline-flex', className)}>
      <span className="sr-only">{etiqueta}</span>
      <span aria-hidden="true" className="isotipo-oscila inline-flex size-20">
        <svg viewBox="0 0 83.66 83.66" className="size-full overflow-visible">
          <path d={TRAZO} fill="none" stroke="var(--color-tinta)" strokeWidth="1.6" strokeLinejoin="round" />
          <path d={TRAZO} fill="var(--color-tinta)" className="isotipo-rellena" />
        </svg>
      </span>
    </div>
  );
}

/** El isotipo centrado sobre el esqueleto de la página, con un velo que lo deja ver al fondo. */
export function VeloCargando() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80">
      <IsotipoCargando etiqueta="Cargando… / Loading…" />
    </div>
  );
}
