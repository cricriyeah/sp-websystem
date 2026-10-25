'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  confirmarCapturaOrden, crearOrden, crearPago, crearPagoOrden, getEstadoReserva, getOrden,
  guardarReserva, type CrearOrdenInput, type OrdenDetalle, type ReservaInput,
} from '@/lib/api';
import { ApiError } from '@/lib/api';
import { clasificar } from '@/lib/errores';
import { tipoDeFallo, type TipoProblema } from '@/lib/problema-reserva';
import { empresaDeFalloCaptura } from '@/lib/fallo-pago';
import { marcarPaginaComoConfirmacion, paginaPideConfirmacion } from '@/lib/marca-confirmacion';
import { borrarPendiente, guardarPendiente } from '@/lib/pendientes';

export type PasoPago = {
  empresaSlug: string;
  monto: string;
  precioTotal?: string;
  clientSecret: string;
  publishableKey: string;
  /** Solo las órdenes de varias empresas vencen: la hora en que se libera si no se completan los pagos. */
  venceEn?: string | null;
};
/** Qué pasó en el último fallo: la empresa (si se sabe), el código del banco y en qué pago ocurrió. */
export type FalloPago = { empresaSlug: string | null; codigo: string; indice: number | null };
export type FasePedido =
  | 'resumiendo' | 'formulario' | 'enviando' | 'pagando' | 'capturando' | 'confirmando' | 'exito' | 'fallo';

type Config = {
  motor: 'reserva' | 'orden';
  sedeSlug: string;
  empresaSlug: string;
  paqueteSlug: string;
  paqueteNombre: string;
  retomarCheckoutId?: string;
  armarPayload: (checkoutId: string) => CrearOrdenInput | ReservaInput;
  formaPago: 'completo' | 'anticipo';
  codigoPromocional?: string;
  captchaToken: () => string;
  mensajeDeError: (err: unknown) => string;
  /** El servidor rechazó un campo concreto: la vista lleva al cliente a su paso y a su control. */
  alErrorDeCampo?: (err: unknown) => void;
  /** Texto cuando la renovacion devuelve otro importe: el cliente debe verlo antes de pagar. */
  mensajeMontoDistinto: (monto: string) => string;
};

type Guardado = { checkoutId?: string; ordenId?: number };
const REINTENTO_MS = 5000;

export function usePagoPedido(config: Config) {
  const clave = `salysol:pedido:${config.paqueteSlug}`;
  const [checkoutId, setCheckoutId] = useState('');
  const [ordenId, setOrdenId] = useState<number | null>(null);
  const [fase, setFase] = useState<FasePedido>('resumiendo');
  const [pagos, setPagos] = useState<PasoPago[]>([]);
  const [indice, setIndice] = useState(0);
  const [error, setError] = useState('');
  // Qué clase de problema es `error`; el aviso del checkout elige título y acción con él.
  // La orden se retomó desde el servidor (recarga o enlace): no hay formulario del cliente que mostrar.
  const [retomado, setRetomado] = useState(false);
  const [errorTipo, setErrorTipo] = useState<TipoProblema | null>(null);
  const [motivoFallo, setMotivoFallo] = useState('');
  const [fallo, setFallo] = useState<FalloPago | null>(null);
  // true si el fallo ocurrió en esta sesión de la página (el formulario sigue en memoria);
  // false al reanudar tras una recarga, donde no hay datos que conservar.
  const [falloEnVivo, setFalloEnVivo] = useState(false);
  const [fallos, setFallos] = useState(0);
  // Solo motor 'reserva': la reserva a renovar y hasta cuando dura el apartado (null = sin apartado).
  const [reservaId, setReservaId] = useState<number | null>(null);
  const [apartadoHasta, setApartadoHasta] = useState<string | null>(null);
  const [confirmandoLargo, setConfirmandoLargo] = useState(false);

  const cfg = useRef(config);
  useEffect(() => {
    cfg.current = config;
  });

  const registrarPendiente = useCallback((id: string, idOrden?: number, retenido = false) => {
    const c = cfg.current;
    guardarPendiente({
      tipo: c.motor, checkoutId: id, ordenId: idOrden,
      sedeSlug: c.sedeSlug, empresaSlug: c.empresaSlug,
      productoSlug: c.paqueteSlug, productoNombre: c.paqueteNombre,
      ruta: window.location.pathname + window.location.search,
      actualizadoEn: new Date().toISOString(),
      tieneDineroRetenido: retenido,
    });
  }, []);

  // En éxito el puntero se queda: la banda global ofrece «Ver confirmación» y «Cerrar». Solo el fallo lo borra.
  useEffect(() => {
    if (checkoutId && fase === 'fallo') borrarPendiente(checkoutId);
  }, [checkoutId, fase]);
  // La confirmación queda en la URL: recargarla la repone, y una entrada nueva al paquete no.
  useEffect(() => {
    if (fase === 'exito') marcarPaginaComoConfirmacion();
  }, [fase]);

  const guardar = useCallback(
    (datos: Guardado) => {
      try {
        window.sessionStorage.setItem(clave, JSON.stringify(datos));
      } catch {
        // sin almacenamiento: si recarga, empieza de cero
      }
    },
    [clave],
  );

  /* eslint-disable react-hooks/set-state-in-effect -- lectura única de sessionStorage en cliente */
  useLayoutEffect(() => {
    let guardado: Guardado | null = null;
    try {
      const crudo = window.sessionStorage.getItem(clave);
      guardado = crudo ? (JSON.parse(crudo) as Guardado) : null;
    } catch {
      guardado = null;
    }
    if (config.retomarCheckoutId) {
      guardado = { checkoutId: config.retomarCheckoutId };
      guardar(guardado);
    }
    if (guardado?.checkoutId) {
      setCheckoutId(guardado.checkoutId);
      if (config.motor === 'orden' && guardado.ordenId) {
        setOrdenId(guardado.ordenId); // el efecto de reanudación de la orden decide la fase
        return;
      }
      if (config.motor === 'reserva') return; // sigue 'resumiendo': el efecto de abajo consulta la reserva
      if (config.retomarCheckoutId && config.motor === 'orden') return;
    } else {
      const nuevo = crypto.randomUUID();
      guardar({ checkoutId: nuevo });
      setCheckoutId(nuevo);
    }
    setFase('formulario');
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al montar
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Motor 'reserva': recuperar el estado de la reserva de este checkout.
  useEffect(() => {
    if (config.motor !== 'reserva' || fase !== 'resumiendo' || !checkoutId) return;
    let cancelado = false;
    getEstadoReserva(checkoutId, config.empresaSlug)
      .then((estado) => {
        if (cancelado) return;
        // Ya pagada: solo se muestra la confirmación si la URL la pide (`?confirmacion=1`, que pone
        // ella misma y el botón «Ver confirmación» de la banda). Sin la marca, esta entrada es para
        // reservar de nuevo: formulario nuevo con otro checkout_id.
        if (estado.estado === 'pagada' && !paginaPideConfirmacion()) {
          const nuevo = crypto.randomUUID();
          guardar({ checkoutId: nuevo });
          setCheckoutId(nuevo);
          setFase('formulario');
          return;
        }
        // 'pendiente_pago' o 'cancelada': se sigue con el formulario; reenviar el mismo
        // checkout_id actualiza la misma reserva (el servidor hace upsert).
        setFase(estado.estado === 'pagada' ? 'exito' : 'formulario');
      })
      .catch(() => {
        if (!cancelado) setFase('formulario'); // 404 o sin red: nunca debe trabar el checkout
      });
    return () => {
      cancelado = true;
    };
  }, [config.motor, config.empresaSlug, fase, checkoutId, guardar]);

  useEffect(() => {
    if (config.motor !== 'orden' || fase !== 'resumiendo' || !checkoutId || ordenId !== null) return;
    let activo = true;
    getOrden(config.sedeSlug, checkoutId)
      .then((detalle) => { if (activo) setOrdenId(detalle.id); })
      .catch(() => { if (activo) setFase('formulario'); });
    return () => { activo = false; };
  }, [config.motor, config.sedeSlug, fase, checkoutId, ordenId]);

  // Motor 'orden': reanudación. El estado real lo dice el servidor.
  useEffect(() => {
    if (ordenId === null) return;
    let cancelado = false;
    getOrden(config.sedeSlug, checkoutId)
      .then((detalle: OrdenDetalle) => {
        if (cancelado) return;
        if (detalle.estado === 'capturada') {
          if (paginaPideConfirmacion()) return setFase('exito');
          // Orden ya cobrada y nadie pidió verla: se reserva de nuevo con un checkout_id nuevo.
          const nuevo = crypto.randomUUID();
          guardar({ checkoutId: nuevo });
          setCheckoutId(nuevo);
          setOrdenId(null);
          return setFase('formulario');
        }
        if (detalle.estado === 'cancelada') return setFase('fallo');
        // Reanudar una orden abierta asegura su puntero de "Continuar reservacion": cubre
        // ordenes creadas antes de que existiera o borradas del localStorage, y deja al dia
        // si ya hay dinero retenido.
        if (checkoutId) {
          registrarPendiente(checkoutId, ordenId, detalle.reservas.some(
            (r) => ['requires_capture', 'succeeded'].includes(r.pago.estado_pi ?? ''),
          ));
        }
        if (detalle.estado === 'autorizando' || detalle.estado === 'autorizada') {
          setPagos(
            detalle.reservas.map((r) => ({
              empresaSlug: r.empresa_slug,
              monto: r.pago.monto ?? '0',
              clientSecret: r.pago.client_secret ?? '',
              publishableKey: r.pago.publishable_key,
              venceEn: detalle.vence_en,
            })),
          );
          const pendiente = detalle.reservas.findIndex(
            (r) => !['requires_capture', 'succeeded'].includes(r.pago.estado_pi ?? ''),
          );
          if (pendiente === -1) return setFase('capturando');
          setIndice(pendiente);
          setRetomado(true);
          return setFase('pagando');
        }
        setFase('formulario'); // 'armando': se creó pero nunca se llegó a crear-pago
      })
      .catch(() => {
        if (cancelado) return;
        try {
          window.sessionStorage.removeItem(clave);
        } catch {
          // nada que limpiar
        }
        setOrdenId(null);
        setFase('formulario');
      });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo cuando cambia ordenId
  }, [ordenId]);

  // Motor 'orden': captura final, con consulta periódica si la respuesta se pierde.
  useEffect(() => {
    if (fase !== 'capturando' || ordenId === null) return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const aplicar = (r: { estado: string; motivo?: string }) => {
      if (cancelado) return true;
      if (r.estado === 'capturada') return setFase('exito'), true;
      if (r.estado === 'cancelada') {
        const motivo = r.motivo ?? '';
        const empresaCaptura = empresaDeFalloCaptura(motivo);
        setMotivoFallo(motivo);
        // Un rechazo de tarjeta ya dejó su propio detalle; solo se completa si falló la captura.
        if (empresaCaptura) setFallo({ empresaSlug: empresaCaptura, codigo: 'captura', indice: null });
        setFalloEnVivo(true);
        setFase('fallo');
        return true;
      }
      return false;
    };
    const consultar = async () => {
      try {
        if (aplicar(await getOrden(config.sedeSlug, checkoutId))) return;
      } catch {
        // una respuesta perdida no prueba que el cobro falló: conservar la orden y seguir consultando
      }
      if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
    };
    confirmarCapturaOrden(config.sedeSlug, ordenId, checkoutId)
      .then((r) => {
        if (!aplicar(r)) timer = setTimeout(consultar, REINTENTO_MS);
      })
      .catch(() => {
        if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
      });
    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [fase, ordenId, checkoutId, config.sedeSlug]);

  // Motor 'reserva': esperar al webhook. Solo `pagada` es éxito; `cancelada` (cupo lleno, reembolso) es fallo.
  useEffect(() => {
    if (fase !== 'confirmando') return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const inicio = Date.now();
    const consultar = async () => {
      try {
        const estado = await getEstadoReserva(checkoutId, config.empresaSlug);
        if (cancelado) return;
        if (estado.estado === 'pagada') return setFase('exito');
        if (estado.estado === 'cancelada') return setMotivoFallo(''), setFalloEnVivo(true), setFase('fallo');
      } catch {
        // sin red: seguir consultando
      }
      if (cancelado) return;
      // Cada 2 s los primeros ~12 s (lo normal es que el webhook ya haya respondido); luego mas espaciado.
      const transcurrido = Date.now() - inicio;
      if (transcurrido > 12000) setConfirmandoLargo(true);
      timer = setTimeout(consultar, transcurrido > 12000 ? REINTENTO_MS : 2000);
    };
    consultar();
    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [fase, checkoutId, config.empresaSlug]);

  // Crea la orden/reserva de `id` y deja el hook listo para pagar. `true` si llegó a 'pagando'.
  const ejecutarEnvio = useCallback(async (id: string): Promise<boolean> => {
    setFase('enviando');
    setError('');
    const c = cfg.current;
    try {
      const payload = c.armarPayload(id);
      if (c.motor === 'orden') {
        const creada = await crearOrden(c.sedeSlug, payload as CrearOrdenInput);
        setOrdenId(creada.orden_id);
        guardar({ checkoutId: id, ordenId: creada.orden_id });
        registrarPendiente(id, creada.orden_id);
        const respuesta = await crearPagoOrden(c.sedeSlug, creada.orden_id, id);
        setPagos(respuesta.map((p) => ({
          empresaSlug: p.empresa_slug, monto: p.monto, clientSecret: p.client_secret, publishableKey: p.publishable_key,
          venceEn: p.vence_en,
        })));
      } else {
        const reserva = await guardarReserva(
          { ...(payload as ReservaInput), captcha_token: c.captchaToken() }, c.empresaSlug,
        );
        registrarPendiente(id);
        const pago = await crearPago(
          reserva.id,
          { checkout_id: id, forma_pago: c.formaPago, codigo_promocional: c.codigoPromocional || undefined },
          c.empresaSlug,
        );
        setReservaId(reserva.id);
        setApartadoHasta(pago.apartado_hasta);
        setPagos([{
          empresaSlug: c.empresaSlug, monto: pago.monto_a_cobrar,
          precioTotal: pago.precio_total,
          clientSecret: pago.client_secret, publishableKey: pago.publishable_key,
        }]);
      }
      setIndice(0);
      setRetomado(false);
      setFase('pagando');
      return true;
    } catch (err) {
      // El cobro ya estaba en marcha (doble clic, otra pestana): no se vuelve a cobrar, se espera al webhook.
      if (c.motor === 'reserva' && err instanceof ApiError) {
        const codigo = (err.detail as Record<string, unknown> | null)?.['codigo'];
        if (codigo === 'pago_en_curso' || codigo === 'ya_no_pendiente') {
          setFase('confirmando');
          return true;
        }
      }
      // Un 503 ("Stripe no configurado") lo traduce `mensajeDeError` a `checkout.paymentUnavailable`.
      setError(c.mensajeDeError(err));
      setErrorTipo(tipoDeFallo(clasificar(err)));
      c.alErrorDeCampo?.(err);
      setFase('formulario');
      return false;
    }
  }, [guardar, registrarPendiente]);

  const enviar = useCallback(async () => {
    if (fase === 'enviando' || fase === 'pagando' || fase === 'capturando' || fase === 'confirmando') return;
    await ejecutarEnvio(checkoutId);
  }, [fase, checkoutId, ejecutarEnvio]);

  const onPagoConfirmado = useCallback(
    () => {
      if (cfg.current.motor === 'orden' && ordenId !== null) {
        registrarPendiente(checkoutId, ordenId, true);
        // La lectura confirma en el servidor la primera retención y permite
        // enviar el enlace de retomar si el siguiente pago sigue pendiente.
        if (indice < pagos.length - 1) {
          void getOrden(cfg.current.sedeSlug, checkoutId).catch(() => undefined);
        }
      }
      if (indice >= pagos.length - 1) {
        // 'orden': hay que capturar todos los pagos autorizados. 'reserva': esperar al webhook.
        setFase(cfg.current.motor === 'orden' ? 'capturando' : 'confirmando');
        return;
      }
      setIndice(indice + 1);
    },
    [indice, pagos.length, ordenId, checkoutId, registrarPendiente],
  );

  /**
   * Se llama en CADA clic de «Pagar», antes de Stripe: renueva el apartado reenviando identicos
   * forma_pago y codigo_promocional (si no, el servidor cambiaria el monto). null = cobrar;
   * texto = no cobrar y mostrarlo; '' = no cobrar, el hook ya cambio de fase.
   */
  const antesDePagar = useCallback(async (): Promise<string | null> => {
    const c = cfg.current;
    const actual = pagos[0];
    if (c.motor !== 'reserva' || reservaId === null || !actual) return null;
    try {
      const renovado = await crearPago(
        reservaId,
        { checkout_id: checkoutId, forma_pago: c.formaPago, codigo_promocional: c.codigoPromocional || undefined },
        c.empresaSlug,
      );
      setApartadoHasta(renovado.apartado_hasta);
      if (Number(renovado.monto_a_cobrar) !== Number(actual.monto)) {
        setPagos([{ ...actual, monto: renovado.monto_a_cobrar, precioTotal: renovado.precio_total }]);
        return c.mensajeMontoDistinto(renovado.monto_a_cobrar);
      }
      return null;
    } catch (err) {
      if (err instanceof ApiError) {
        const codigo = (err.detail as Record<string, unknown> | null)?.['codigo'];
        if (codigo === 'sin_cupo') {
          setError(c.mensajeDeError(err));
          setErrorTipo('sin_cupo');
          setPagos([]);
          setApartadoHasta(null);
          setFase('formulario');
          return '';
        }
        if (codigo === 'pago_en_curso' || codigo === 'ya_no_pendiente') {
          setFase('confirmando');
          return '';
        }
      }
      return c.mensajeDeError(err);
    }
  }, [pagos, reservaId, checkoutId]);

  const onPagoRechazado = useCallback((mensaje: string, codigo?: string) => {
    setMotivoFallo(mensaje);
    if (cfg.current.motor === 'orden') {
      setFallo({ empresaSlug: pagos[indice]?.empresaSlug ?? null, codigo: codigo ?? '', indice });
      setFallos((n) => n + 1);
      // pedir confirmar-captura revierte la orden incompleta (void del primer pago)
      setFase('capturando');
    }
    // Reserva de una sola empresa: el cliente se queda en el formulario de tarjeta. Antes la fase volvia a
    // «formulario», o sea al paso «Cómo pagas», que pedia otra vez la verificación y mostraba un error aparte;
    // el aviso con el motivo y «Probar otra tarjeta» ya lo pinta el propio formulario de pago.
  }, [indice, pagos]);

  // La orden/reserva anterior quedó cancelada en el servidor y su checkout_id ya está
  // ligado a ella: un intento nuevo necesita un checkout_id propio. El formulario vive
  // en el componente de la página y no se toca.
  const soltarIntentoAnterior = useCallback(() => {
    borrarPendiente(checkoutId);
    const nuevo = crypto.randomUUID();
    setCheckoutId(nuevo);
    guardar({ checkoutId: nuevo });
    setOrdenId(null);
    setPagos([]);
    setReservaId(null);
    setApartadoHasta(null);
    setConfirmandoLargo(false);
    setIndice(0);
    setMotivoFallo('');
    setFallo(null);
    setFalloEnVivo(false);
    setError('');
    return nuevo;
  }, [guardar, checkoutId]);

  /** Vuelve al formulario con lo que el cliente ya llenó (sin recargar la página). */
  const reiniciar = useCallback(() => {
    soltarIntentoAnterior();
    setFase('formulario');
  }, [soltarIntentoAnterior]);

  /** Crea una orden nueva y lleva directo al pago. `false` si no pudo (el error queda en `error`). */
  const reintentar = useCallback(
    () => ejecutarEnvio(soltarIntentoAnterior()),
    [ejecutarEnvio, soltarIntentoAnterior],
  );

  return {
    fase, pagos, indice, error, errorTipo, retomado, motivoFallo, ordenId, checkoutId, reservaId,
    fallo, falloEnVivo, fallos, apartadoHasta, confirmandoLargo,
    enviar, antesDePagar, onPagoConfirmado, onPagoRechazado, reiniciar, reintentar,
  };
}
