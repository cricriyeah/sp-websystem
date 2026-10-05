import { useState, type ReactNode } from 'react';
import { CaretDown, Check } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { EtiquetaModificar } from '@/components/checkout/accion-terciaria';
import { PieDeTarjeta } from '@/components/checkout/pie-tarjeta';

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
   * ("Cambiar") para reabrirla. Es un renglón de una línea: varias seguidas
   * se ven como un solo bloque compacto (`unidaConAnterior`).
   * 'suspendido': la tarjeta que estaba activa mientras el cliente corrige una
   * respuesta anterior: solo su título, sin cuerpo, hasta que termine.
   *
   * El numero de paso ya no vive en esta tarjeta — antes era un circulo con
   * numero que decia lo mismo que la linea verde de abajo y ahora tambien el
   * `CheckoutStepper` de arriba; tres senales del mismo progreso. El stepper
   * es la unica que queda.
   */
  estado?: 'activo' | 'editando' | 'completado' | 'suspendido';
  /** Colapsado: la respuesta ya dada, en una linea. */
  resumen?: ReactNode;
  /** Texto del boton del encabezado ("Cambiar" / "Listo" segun `estado`). */
  actionLabel?: string;
  onAction?: () => void;
  /** Empresa del grupo (solo cuando el pedido tiene más de una): una sola vez, junto al título. */
  etiqueta?: string;
  /** Fila final de la tarjeta abierta con el único CTA primario. Solo en `activo`. */
  pie?: ReactNode;
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
  etiqueta,
  pie,
  children,
}: CheckoutSectionCardProps) {
  const abierto = estado === 'activo' || estado === 'editando';
  const confirmado = estado === 'completado' || estado === 'editando';
  const enRenglon = estado === 'completado' && variant === 'flat';
  const sinMovimiento = useReducedMotion();
  // `overflow-hidden` solo hace falta MIENTRAS la altura esta en un valor
  // intermedio (la transicion de 0 a 'auto'): asentada, el cuadro ya mide lo
  // que su contenido necesita y no hay nada que recortar. Dejarlo puesto
  // siempre le cortaba cualquier cosa que un hijo pintara fuera de su propia
  // caja — un box-shadow de foco, un anillo de pulso — contra el borde exacto
  // del padding, sin aviso.
  const [enTransicion, setEnTransicion] = useState(false);

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
        {enRenglon ? (
          <span className="flex min-w-0 items-center gap-x-2 text-sm">
            <span className="min-w-0 truncate font-sans font-medium tracking-tight text-foreground">{title}</span>
            {etiqueta && (
              // En pantallas angostas el renglón no tiene sitio para la empresa
              // sin pisar "Modificar": se ve completa al abrir la tarjeta.
              <span className="hidden shrink-0 rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-muted sm:inline">
                {etiqueta}
              </span>
            )}
            {resumen && <span className="min-w-0 truncate text-muted">· {resumen}</span>}
          </span>
        ) : (
          <span className="flex min-w-0 flex-col">
            <span className="flex min-w-0 flex-wrap items-center gap-x-2">
              <span className="font-sans text-sm font-medium tracking-tight text-foreground">
                {title}
              </span>
              {etiqueta && (
                <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-muted">
                  {etiqueta}
                </span>
              )}
            </span>
          </span>
        )}
      </span>

      {actionLabel && onAction && enRenglon && (
        // Secundario: un renglón de respuesta no debe competir con el CTA de la
        // tarjeta activa. El renglón entero es el botón; la etiqueta solo lo dice.
        <EtiquetaModificar>{actionLabel}</EtiquetaModificar>
      )}
      {actionLabel && onAction && !enRenglon && (
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

  if (estado === 'suspendido') {
    return (
      <section className="border border-dashed border-border bg-background px-5 py-3 sm:px-6">
        <p className="flex items-center gap-x-2 text-sm font-medium text-muted">
          {title}
          {etiqueta && (
            <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium">{etiqueta}</span>
          )}
        </p>
      </section>
    );
  }

  return (
    <section
      // La tarjeta en foco (activa o en edición) se marca para que el scroll
      // automático sepa a cuál llevar al cliente; `scroll-mt` deja libre el
      // header fijo y el stepper.
      data-tarjeta-foco={abierto ? '' : undefined}
      className={`scroll-mt-[calc(var(--nav-alto)+3.5rem)] border lg:scroll-mt-[calc(var(--nav-alto)+5rem)] ${ESTILOS[variant]} ${
        abierto ? 'p-6 sm:p-8' : enRenglon ? 'px-5 py-3 sm:px-6' : 'p-5 sm:p-6'
      }`}
    >
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
            onAnimationStart={() => setEnTransicion(true)}
            onAnimationComplete={() => setEnTransicion(false)}
            className={enTransicion ? 'overflow-hidden' : 'overflow-visible'}
          >
            <div className={`mt-5 ${variant === 'flat' ? 'flex flex-col gap-5' : ''}`}>{children}</div>
            {pie && <PieDeTarjeta titulo={title}>{pie}</PieDeTarjeta>}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/**
 * Un bloque de la tarjeta: una pregunta, con su título corto opcional. El
 * espacio entre bloques lo pone el cuerpo de la tarjeta (`gap-5`), no rayas.
 * `opcional` es el texto de la etiqueta ("Opcional") — se pasa traducido.
 */
export function BloqueDePaso({
  titulo,
  opcional,
  children,
}: {
  titulo?: string;
  opcional?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {titulo && (
        <p className="text-sm font-medium text-foreground">
          {titulo}
          {opcional && <span className="ml-2 text-xs font-normal text-muted">{opcional}</span>}
        </p>
      )}
      {children}
    </div>
  );
}
