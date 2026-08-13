'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

type FieldPopoverProps = {
  label: string;
  value: string;
  icon: ReactNode;
  /**
   * Alto aproximado del panel, en px. Se usa al abrir para decidir si cabe
   * hacia abajo: no se puede medir el panel antes de pintarlo, y esperar a
   * medirlo provocaria que salte de posicion a la vista del usuario.
   */
  alturaEstimada: number;
  /** Recibe `cerrar` para que al elegir una opcion el panel se cierre solo. */
  children: (cerrar: () => void) => ReactNode;
};

/**
 * Campo del booking bar que abre un panel: se usa para el calendario y para la
 * hora. Reemplaza a `<input type="date">` y `<select>`, cuyos desplegables los
 * pinta el sistema operativo y no se pueden llevar al diseño del sitio.
 *
 * Se encarga de lo aburrido pero necesario: cerrar al hacer clic fuera, cerrar
 * con Escape y devolver el foco al boton para que se pueda usar con teclado.
 */
export function FieldPopover({ label, value, icon, alturaEstimada, children }: FieldPopoverProps) {
  const [open, setOpen] = useState(false);
  const [haciaArriba, setHaciaArriba] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);
  const disparador = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  /**
   * Decide de que lado abrir. Se mide aqui, en el manejador del clic, y no en un
   * efecto: asi el panel aparece ya en su sitio en vez de pintarse abajo y
   * brincar arriba.
   */
  const alternar = () => {
    if (!open) {
      const caja = disparador.current?.getBoundingClientRect();
      if (caja) {
        const espacioAbajo = window.innerHeight - caja.bottom;
        // Solo se sube si de verdad no cabe abajo Y arriba hay mas lugar.
        setHaciaArriba(espacioAbajo < alturaEstimada && caja.top > espacioAbajo);
      }
    }
    setOpen((v) => !v);
  };

  // Solo cambia estado: se lo pasamos a `children`, que corre en render, y una
  // funcion que tocara refs ahi dentro dispara la regla react-hooks/refs.
  const cerrar = () => setOpen(false);

  useEffect(() => {
    if (!open) return;

    const alClicFuera = (event: PointerEvent) => {
      if (!contenedor.current?.contains(event.target as Node)) setOpen(false);
    };
    // Escape devuelve el foco al boton para no dejar al usuario de teclado
    // perdido al final del documento. Al hacer clic fuera no: ahi el foco ya es
    // de donde el usuario decidio ir.
    const alTeclear = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        disparador.current?.focus();
      }
    };

    document.addEventListener('pointerdown', alClicFuera);
    document.addEventListener('keydown', alTeclear);
    return () => {
      document.removeEventListener('pointerdown', alClicFuera);
      document.removeEventListener('keydown', alTeclear);
    };
  }, [open]);

  return (
    <div ref={contenedor} className="relative flex flex-1">
      <button
        ref={disparador}
        type="button"
        onClick={alternar}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        className="flex flex-1 items-center gap-3 rounded-2xl px-6 py-4 text-left transition-colors hover:bg-background sm:rounded-none"
      >
        {icon}
        <span className="flex flex-col items-start gap-0.5">
          <span className="text-xs text-muted">{label}</span>
          <span className="text-sm whitespace-nowrap text-foreground">{value}</span>
        </span>
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label={label}
          // max-h + scroll para la pantalla en la que no cabe ni arriba ni abajo.
          className={`absolute left-0 z-30 max-h-[70vh] overflow-y-auto rounded-2xl border border-border bg-surface p-4 text-left shadow-[0_16px_40px_rgba(11,36,32,0.18)] ${
            haciaArriba ? 'bottom-full mb-2' : 'top-full mt-2'
          }`}
        >
          {children(cerrar)}
        </div>
      )}
    </div>
  );
}
