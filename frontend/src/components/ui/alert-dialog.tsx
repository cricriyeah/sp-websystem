'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button } from './button';
import { cn } from './cn';
import { alertaClases } from './variantes';

type AlertDialogProps = {
  abierto: boolean;
  titulo: string;
  cuerpo: ReactNode;
  /** La salida segura («Seguir con mi reserva»): va primero en el DOM y recibe el foco inicial. */
  etiquetaSegura: string;
  /** La acción destructiva, con el nombre de su resultado («Cancelar mi orden»). */
  etiquetaDestructiva: string;
  /** Salida segura. También es lo que hace Esc: cancelar nunca destruye. */
  onSegura: () => void;
  onDestructiva: () => void;
  className?: string;
};

/**
 * Confirmación de una acción destructiva (la skill de shadcn pide `AlertDialog`, no
 * `Dialog`, para esto). Sobre `<dialog role="alertdialog">` + `showModal()`: foco
 * atrapado, resto de la página inerte, foco de vuelta al disparador al cerrar.
 *
 * - La salida segura va primero en el DOM, con variante `secundario`, y es la que
 *   recibe el foco: Enter al abrir no destruye nada.
 * - Solo la destructiva usa `peligro`. Nunca hay dos botones `principal`.
 * - Tocar fuera NO cierra (no es una respuesta); Esc equivale a la salida segura.
 *
 * Controlado: el padre manda `abierto` y lo pone en false en ambos callbacks.
 */
export function AlertDialog({
  abierto,
  titulo,
  cuerpo,
  etiquetaSegura,
  etiquetaDestructiva,
  onSegura,
  onDestructiva,
  className,
}: AlertDialogProps) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const idTitulo = useId();
  const idCuerpo = useId();
  const clases = alertaClases();

  // Último valor de `abierto` para el evento `close`: un cierre pedido por el padre
  // ya viene con `abierto` en false y no cuenta como un Esc.
  const abiertoActual = useRef(abierto);

  useEffect(() => {
    abiertoActual.current = abierto;
    const el = dialogo.current;
    if (!el) return;
    if (abierto && !el.open) {
      el.showModal();
      // Explícito: el foco inicial es la salida segura aunque cambie el orden del DOM.
      el.querySelector<HTMLElement>('[data-foco-inicial]')?.focus();
    }
    if (!abierto && el.open) el.close();
  }, [abierto]);

  return (
    <dialog
      ref={dialogo}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={idTitulo}
      aria-describedby={idCuerpo}
      onClose={() => {
        if (abiertoActual.current) onSegura();
      }}
      className={cn(clases.dialogo, className)}
    >
      <h2 id={idTitulo} className={cn('texto-subtitulo', clases.titulo)}>
        {titulo}
      </h2>
      <div id={idCuerpo} className={clases.cuerpo}>
        {cuerpo}
      </div>
      <div className={clases.acciones}>
        <Button variante="secundario" data-foco-inicial="" onClick={onSegura} className={clases.boton}>
          {etiquetaSegura}
        </Button>
        <Button variante="peligro" onClick={onDestructiva} className={clases.boton}>
          {etiquetaDestructiva}
        </Button>
      </div>
    </dialog>
  );
}
