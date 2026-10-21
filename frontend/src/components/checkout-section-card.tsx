import { useState, type ReactNode } from 'react';
import { CaretDown, Check } from '@phosphor-icons/react';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import { transicion } from '@/lib/movimiento';
import { numeroDePaso, type PasoId } from '@/lib/pasos-checkout';
import { Button } from '@/components/ui/button';
import { EtiquetaModificar, FLECHA } from '@/components/checkout/accion-terciaria';
import { useDetalleAbierto } from '@/components/checkout/detalle-abierto';
import { PieDeTarjeta } from '@/components/checkout/pie-tarjeta';
import { useEnAsistente } from '@/components/reserva/asistente-movil';

type CheckoutSectionCardProps = {
  title: string;
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
   */
  estado?: 'activo' | 'editando' | 'completado' | 'suspendido';
  /** El paso del checkout que es esta tarjeta: su número va en un círculo negro antes del título. Sin él (un grupo de servicio), solo el título. */
  paso?: PasoId;
  /**
   * Solo lectura: si el renglón completado no se puede reabrir (`onAction` sin
   * poner) pero trae `detalle`, se abre para leer cada dato en su propia línea
   * (etiqueta y valor) en vez de solo el resumen cortado.
   */
  detalle?: { etiqueta: string; valor: ReactNode }[];
  /** Texto del boton del encabezado ("Cambiar" / "Listo" segun `estado`). */
  actionLabel?: string;
  onAction?: () => void;
  /**
   * Empresa del grupo (solo cuando el pedido tiene más de una): una sola vez, junto al título.
   * Texto (se pinta como chip) o un nodo ya armado, p. ej. el `EmpresaSello` con su nombre.
   */
  etiqueta?: ReactNode;
  /** Fila final de la tarjeta abierta con el único CTA primario. Solo en `activo`. */
  pie?: ReactNode;
  children: ReactNode;
};

const ESTILOS = 'bg-superficie shadow-tarjeta';
/** El número del paso: círculo negro con el número en la voz de los titulares. */
const NUMERO = 'inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-tinta font-display texto-subtitulo text-white';
/** La empresa como texto: un chip. Como `EmpresaSello`, ya trae su propia forma. */
const CHIP = 'rounded-full bg-cafe-bruma px-3 py-1 texto-pie font-semibold text-foreground';

export function CheckoutSectionCard({
  title,
  estado = 'activo',
  paso,
  detalle,
  actionLabel,
  onAction,
  etiqueta,
  pie,
  children,
}: CheckoutSectionCardProps) {
  const abierto = estado === 'activo' || estado === 'editando';
  const enRenglon = estado === 'completado';
  const conDetalle = enRenglon && !onAction && !!detalle && detalle.length > 0;
  const verDetalle = useDetalleAbierto();
  const detalleAbierto = conDetalle && verDetalle.abierto;
  const sinMovimiento = useReducedMotion();
  // `overflow-hidden` solo hace falta MIENTRAS la altura esta en un valor
  // intermedio (la transicion de 0 a 'auto'): asentada, el cuadro ya mide lo
  // que su contenido necesita y no hay nada que recortar. Dejarlo puesto
  // siempre le cortaba cualquier cosa que un hijo pintara fuera de su propia
  // caja — un box-shadow de foco, un anillo de pulso — contra el borde exacto
  // del padding, sin aviso.
  const [enTransicion, setEnTransicion] = useState(false);
  const enAsistente = useEnAsistente();

  // Dentro de una pantalla del asistente móvil la tarjeta no tiene marco, título ni pie: la pantalla
  // pone el título y el botón vive en la barra. Una respuesta ya dada no se pinta.
  if (enAsistente) {
    if (!abierto) return null;
    return <div className="flex flex-col gap-5 bg-superficie p-4">{children}</div>;
  }

  const encabezado = (
    <>
      <span className="flex min-w-0 items-center gap-4">
        {paso && (
          <span aria-hidden="true" className={NUMERO}>
            {numeroDePaso(paso)}
          </span>
        )}
        <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <span className="texto-paso text-foreground">{title}</span>
          {etiqueta && (
            // En pantallas angostas el renglón no tiene sitio para la empresa sin pisar «Modificar»: se
            // ve completa al abrir la tarjeta.
            <span className={`${enRenglon ? 'hidden sm:inline-flex' : 'inline-flex'} shrink-0 ${typeof etiqueta === 'string' ? CHIP : ''}`}>
              {etiqueta}
            </span>
          )}
        </span>
      </span>

      {conDetalle && (
        <CaretDown
          size={16}
          weight="bold"
          aria-hidden
          className={`shrink-0 text-foreground transition-transform duration-[var(--duracion-media)] ${detalleAbierto ? 'rotate-180' : ''}`}
        />
      )}
      {actionLabel && onAction && enRenglon && (
        // Secundario: un renglón de respuesta no debe competir con el CTA de la tarjeta activa. El
        // renglón entero es el botón; la etiqueta solo lo dice.
        <EtiquetaModificar>{actionLabel}</EtiquetaModificar>
      )}
      {actionLabel && onAction && !enRenglon && (
        estado === 'editando' ? (
          // «Listo» es el CTA primario de una tarjeta que se reabrió: confirma y sigue. Es el mismo negro
          // que `BotonPaso`, para que se lea como «el siguiente paso» y no como un control secundario.
          <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-tinta px-5 py-2.5 texto-etiqueta text-white transition-colors group-hover:bg-cafe">
            {actionLabel}
            <Check size={16} weight="bold" aria-hidden />
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-2 texto-etiqueta text-foreground">
            {actionLabel}
            <span className={FLECHA}>
              <CaretDown size={16} weight="bold" className={`transition-transform duration-[var(--duracion-media)] ${abierto ? 'rotate-180' : ''}`} />
            </span>
          </span>
        )
      )}
    </>
  );

  if (estado === 'suspendido') {
    return (
      <section className={`${ESTILOS} px-5 py-4 sm:px-8`}>
        <div className="flex items-center gap-4">
          {paso && (
            <span aria-hidden="true" className={NUMERO}>
              {numeroDePaso(paso)}
            </span>
          )}
          <p className="flex flex-wrap items-center gap-x-3 texto-paso text-foreground">
            {title}
            {etiqueta && (
              <span className={`inline-flex ${typeof etiqueta === 'string' ? CHIP : ''}`}>{etiqueta}</span>
            )}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      // La tarjeta en foco (activa o en edición) se marca para que el scroll
      // automático sepa a cuál llevar al cliente; `scroll-mt` deja libre el
      // header fijo y el stepper.
      data-tarjeta-foco={abierto ? '' : undefined}
      className={`scroll-mt-[calc(var(--nav-alto)+3.5rem)] lg:scroll-mt-[calc(var(--nav-alto)+5rem)] ${ESTILOS} ${
        abierto ? 'p-6 sm:p-8' : enRenglon ? 'px-5 py-4 sm:px-8' : 'p-5 sm:p-6'
      }`}
    >
      {/* El encabezado es boton solo si de verdad hace algo. El paso 3 una
          vez bloqueado el pago (`onAction` sin poner) queda como fila
          informativa: un boton que no responde al click es la misma mentira
          que un CTA que no cumple lo que promete. */}
      {onAction ? (
        <Button
          variante="libre"
          type="button"
          onClick={onAction}
          aria-expanded={abierto}
          className="group flex w-full items-center justify-between gap-4 text-left"
        >
          {encabezado}
        </Button>
      ) : conDetalle ? (
        <Button
          variante="libre"
          type="button"
          onClick={verDetalle.alternar}
          aria-expanded={detalleAbierto}
          aria-controls={verDetalle.id}
          className="group flex min-h-11 w-full items-center justify-between gap-4 text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
        >
          {encabezado}
        </Button>
      ) : (
        <div className="flex w-full items-center justify-between gap-4 text-left">{encabezado}</div>
      )}

      {conDetalle && (
        // Altura animada con la cuadrícula (0fr a 1fr): se abre y se pliega sin medir nada.
        <div
          id={verDetalle.id}
          className={`grid transition-[grid-template-rows,opacity,visibility] duration-[var(--duracion-media)] ease-[var(--curva-estandar)] motion-reduce:transition-none ${
            detalleAbierto ? 'visible grid-rows-[1fr] opacity-100' : 'invisible grid-rows-[0fr] opacity-0'
          }`}
        >
          <div className="min-h-0 overflow-hidden">
            <dl className="mt-3 grid grid-cols-[6.5rem_minmax(0,1fr)] gap-x-4 gap-y-2 pb-2 texto-cuerpo">
              {detalle!.map((linea) => (
                <div key={linea.etiqueta} className="contents">
                  <dt className="font-semibold">{linea.etiqueta}</dt>
                  <dd className="min-w-0 break-words text-foreground">{linea.valor}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      <AnimatePresence initial={false}>
        {abierto && (
          <m.div
            key="contenido"
            initial={sinMovimiento ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={transicion(sinMovimiento)}
            onAnimationStart={() => setEnTransicion(true)}
            onAnimationComplete={() => setEnTransicion(false)}
            className={enTransicion ? 'overflow-hidden' : 'overflow-visible'}
          >
            <div className={`mt-5 flex flex-col gap-5`}>{children}</div>
            {pie && <PieDeTarjeta titulo={title}>{pie}</PieDeTarjeta>}
          </m.div>
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
        <p className="texto-cuerpo font-semibold text-foreground">
          {titulo}
          {opcional && <span className="ml-2 texto-cuerpo font-normal text-foreground">{opcional}</span>}
        </p>
      )}
      {children}
    </div>
  );
}
