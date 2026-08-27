import type { ReactNode } from 'react';
import { CaretDown, Check } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

type CheckoutSectionCardProps = {
  title: string;
  /**
   * `flat` (pasos): tarjeta blanca al ras. `elevated` (resumen de pago): la
   * misma tarjeta pero con sombra marcada, para que la columna del dinero se
   * lea como una pieza aparte y no como un paso mas de la lista.
   */
  variant?: 'flat' | 'elevated';
  /**
   * 'activo': tarjeta abierta, primera vez que se contesta — sin boton en el
   * encabezado, el CTA para avanzar vive adentro (`children`).
   * 'editando': abierta de nuevo despues de estar confirmada. Header lleva
   * `actionLabel` ("Listo") para volver a colapsarla sin repetir la
   * validacion — lo que haya adentro ya es valido, solo se estaba corrigiendo.
   * 'completado': colapsada a un renglon con `resumen` y `actionLabel`
   * ("Cambiar") para reabrirla.
   *
   * El numero de paso ya no vive en esta tarjeta — antes era un circulo con
   * numero que decia lo mismo que la linea verde de abajo y ahora tambien el
   * `CheckoutStepper` de arriba; tres senales del mismo progreso. El stepper
   * es la unica que queda.
   */
  estado?: 'activo' | 'editando' | 'completado';
  /** Colapsado: la respuesta ya dada, en una linea. */
  resumen?: ReactNode;
  /** Texto del boton del encabezado ("Cambiar" / "Listo" segun `estado`). */
  actionLabel?: string;
  onAction?: () => void;
  children: ReactNode;
};

const ESTILOS = {
  flat: 'border-border bg-background',
  elevated: 'border-border bg-background shadow-[0_18px_45px_rgba(11,36,32,0.16)]',
};

export function CheckoutSectionCard({
  title,
  variant = 'flat',
  estado = 'activo',
  resumen,
  actionLabel,
  onAction,
  children,
}: CheckoutSectionCardProps) {
  const abierto = estado !== 'completado';
  const confirmado = estado !== 'activo';
  const sinMovimiento = useReducedMotion();

  const encabezado = (
    <>
      <span className="flex min-w-0 items-center gap-3">
        {/* El check solo aparece una vez confirmado — es la unica pista de
            "esto ya quedo" que le queda a la tarjeta abierta para editar, y
            la que reemplaza el circulo numerado que traia antes. */}
        {confirmado && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-exito-fondo text-exito">
            <Check size={13} weight="bold" />
          </span>
        )}
        <span className="flex min-w-0 flex-col">
          <span className="font-sans text-sm font-medium tracking-tight text-foreground">
            {title}
          </span>
          {!abierto && resumen && (
            <span className="block truncate text-xs text-muted">{resumen}</span>
          )}
        </span>
      </span>

      {actionLabel && onAction && (
        <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition-colors group-hover:border-accent group-hover:text-accent">
          {actionLabel}
          {/* Apunta hacia donde lleva el click: abajo cuando abrir revela mas,
              arriba cuando ya esta abierta y el click la cierra. La rotacion
              es lo que hace obvio que es la MISMA flecha, no un icono
              distinto por estado. */}
          <CaretDown
            size={12}
            weight="bold"
            className={`transition-transform duration-300 ${abierto ? 'rotate-180' : ''}`}
          />
        </span>
      )}
    </>
  );

  return (
    <section className={`border ${ESTILOS[variant]} ${abierto ? 'p-6 sm:p-8' : 'p-5 sm:p-6'}`}>
      {/* El encabezado es boton solo si de verdad hace algo. El paso 3 una
          vez bloqueado el pago (`onAction` sin poner) queda como fila
          informativa: un boton que no responde al click es la misma mentira
          que un CTA que no cumple lo que promete. */}
      {onAction ? (
        <button
          type="button"
          onClick={onAction}
          aria-expanded={abierto}
          className="group flex w-full items-center justify-between gap-4 text-left"
        >
          {encabezado}
        </button>
      ) : (
        <div className="flex w-full items-center justify-between gap-4 text-left">{encabezado}</div>
      )}

      <AnimatePresence initial={false}>
        {abierto && (
          <motion.div
            key="contenido"
            initial={sinMovimiento ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="mt-5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
