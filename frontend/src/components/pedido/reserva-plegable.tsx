'use client';

import { useId, useState, type ReactNode } from 'react';
import { CaretLeft, Lock, WhatsappLogo } from '@phosphor-icons/react';
import { DetalleAbiertoContexto, useProveedorDetalle } from '@/components/checkout/detalle-abierto';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

/**
 * Las respuestas ya dadas, cuando el pago ya se creó y no se pueden cambiar.
 *
 * Son varios renglones que empujan el formulario de tarjeta (unos 220 px en
 * móvil) y repiten lo que el cliente ya sabe, así que se pliegan en uno solo
 * ("Tu reserva" + lo esencial) que se abre para ver el detalle, en móvil y en
 * escritorio. Es un solo árbol de renglones: solo cambia si se ven.
 *
 * El encabezado lleva el estado ("Guardada", con candado y en acento, no en verde:
 * el verde es "completado" y el pago todavía falta) y, abierto, deja de repetir el
 * resumen que los renglones ya muestran. Al final dice por qué ya no se pueden
 * editar y a quién escribir si algo está mal: un renglón que no responde sin
 * explicar nada se lee como un fallo.
 */
export function NotaBloqueada({
  nota,
  ctaAyuda,
  mensajeAyuda,
  className,
}: {
  nota: string;
  ctaAyuda: string;
  mensajeAyuda: string;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-3 text-xs leading-relaxed text-muted sm:flex-row sm:items-center sm:justify-between sm:gap-4 ${className ?? ''}`}>
      <p>{nota}</p>
      {tieneWhatsapp && (
        // Mismo verde y logo que el botón flotante de ayuda: es la misma acción y se debe
        // reconocer sin leer. Texto blanco, igual que el flotante.
        <a
          href={whatsappHref(mensajeAyuda)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-9 shrink-0 items-center justify-center gap-1.5 self-start rounded-full bg-[#25D366] px-4 py-1.5 text-xs font-medium text-white transition-transform hover:scale-[1.02] active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:self-auto"
        >
          <WhatsappLogo size={16} weight="fill" aria-hidden />
          {ctaAyuda}
        </a>
      )}
    </div>
  );
}

export function ReservaPlegable({
  titulo,
  etiquetaEstado,
  resumen,
  notaBloqueada,
  ctaAyuda,
  mensajeAyuda,
  activo = true,
  children,
}: {
  titulo: string;
  /** El estado de la reserva ("Guardada"), junto al título. */
  etiquetaEstado: string;
  resumen: string;
  notaBloqueada: string;
  ctaAyuda: string;
  mensajeAyuda: string;
  /** Falso mientras el cliente todavía llena los pasos: no pliega nada, los hijos no se remontan al activarse. */
  activo?: boolean;
  children: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const id = useId();
  const detalle = useProveedorDetalle();

  return (
    <DetalleAbiertoContexto.Provider value={detalle}>
    <div>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        aria-controls={id}
        className={`group flex min-h-11 w-full items-center justify-between gap-4 border border-border bg-background px-5 py-2 text-left text-sm transition-colors hover:bg-surface active:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${activo ? '' : 'hidden'}`}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 font-medium tracking-tight text-foreground">{titulo}</span>
          <span className="flex shrink-0 items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--accent)_10%,var(--background))] px-2 py-0.5 text-[11px] font-medium text-accent">
            <Lock size={11} weight="bold" aria-hidden />
            {etiquetaEstado}
          </span>
          {/* Abierto, el detalle de abajo ya lo dice: el resumen se desvanece sin mover el chip. */}
          <span
            aria-hidden={abierto}
            className={`min-w-0 truncate text-muted transition-opacity duration-300 motion-reduce:transition-none ${abierto ? 'opacity-0' : ''}`}
          >
            · {resumen}
          </span>
        </span>
        <CaretLeft
          size={12}
          weight="bold"
          className={`shrink-0 text-muted transition-transform duration-300 ${abierto ? '-rotate-90' : ''}`}
        />
      </button>

      {/* Altura animada con la cuadrícula (0fr → 1fr): se abre y se pliega sin
          medir nada ni desmontar los renglones. */}
      <div
        id={id}
        className={`grid transition-[grid-template-rows,opacity,margin,visibility] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none ${
          abierto || !activo ? `visible grid-rows-[1fr] opacity-100 ${activo ? 'mt-2' : 'mt-0'}` : 'invisible mt-0 grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className={`min-h-0 ${activo ? 'overflow-hidden' : 'overflow-visible'}`}>
          {/* La marca de "completado" de cada renglón sobra: el candado del encabezado ya dice el estado. */}
          <div className={`flex flex-col gap-6 ${activo ? '[&_.marca-paso]:hidden' : ''}`}>
            {children}
            {/* Pie del grupo: pegado al último renglón (mismo -mt-4 que los renglones unidos) y en caja,
                para que se lea como parte de la reserva y no como texto suelto. */}
            {activo && (
              <NotaBloqueada
                nota={notaBloqueada} ctaAyuda={ctaAyuda} mensajeAyuda={mensajeAyuda}
                className="-mt-4 border border-border bg-background px-5 py-3 sm:px-6"
              />
            )}
          </div>
        </div>
      </div>
    </div>
    </DetalleAbiertoContexto.Provider>
  );
}
