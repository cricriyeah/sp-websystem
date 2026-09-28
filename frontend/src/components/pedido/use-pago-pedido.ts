'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  confirmarCapturaOrden, crearOrden, crearPago, crearPagoOrden, getEstadoReserva, getOrden,
  guardarReserva, type CrearOrdenInput, type OrdenDetalle, type ReservaInput,
} from '@/lib/api';

export type PasoPago = { empresaSlug: string; monto: string; clientSecret: string; publishableKey: string };
export type FasePedido =
  | 'resumiendo' | 'formulario' | 'enviando' | 'pagando' | 'capturando' | 'confirmando' | 'exito' | 'fallo';

type Config = {
  motor: 'reserva' | 'orden';
  sedeSlug: string;
  empresaSlug: string;
  paqueteSlug: string;
  armarPayload: (checkoutId: string) => CrearOrdenInput | ReservaInput;
  formaPago: 'completo' | 'anticipo';
  codigoPromocional?: string;
  captchaToken: () => string;
  mensajeDeError: (err: unknown) => string;
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
  const [motivoFallo, setMotivoFallo] = useState('');

  const cfg = useRef(config);
  useEffect(() => {
    cfg.current = config;
  });

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
    if (guardado?.checkoutId) {
      setCheckoutId(guardado.checkoutId);
      if (config.motor === 'orden' && guardado.ordenId) {
        setOrdenId(guardado.ordenId); // el efecto de reanudación de la orden decide la fase
        return;
      }
      if (config.motor === 'reserva') return; // sigue 'resumiendo': el efecto de abajo consulta la reserva
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
  }, [config.motor, config.empresaSlug, fase, checkoutId]);

  // Motor 'orden': reanudación. El estado real lo dice el servidor.
  useEffect(() => {
    if (ordenId === null) return;
    let cancelado = false;
    getOrden(config.sedeSlug, ordenId)
      .then((detalle: OrdenDetalle) => {
        if (cancelado) return;
        if (detalle.estado === 'capturada') return setFase('exito');
        if (detalle.estado === 'cancelada') return setFase('fallo');
        if (detalle.estado === 'autorizando' || detalle.estado === 'autorizada') {
          setPagos(
            detalle.reservas.map((r) => ({
              empresaSlug: r.empresa_slug,
              monto: r.pago.monto ?? '0',
              clientSecret: r.pago.client_secret ?? '',
              publishableKey: r.pago.publishable_key,
            })),
          );
          const pendiente = detalle.reservas.findIndex(
            (r) => !['requires_capture', 'succeeded'].includes(r.pago.estado_pi ?? ''),
          );
          if (pendiente === -1) return setFase('capturando');
          setIndice(pendiente);
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
      if (r.estado === 'cancelada') return setMotivoFallo(r.motivo ?? ''), setFase('fallo'), true;
      return false;
    };
    const consultar = async () => {
      try {
        if (aplicar(await getOrden(config.sedeSlug, ordenId))) return;
      } catch {
        // una respuesta perdida no prueba que el cobro falló: conservar la orden y seguir consultando
      }
      if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
    };
    confirmarCapturaOrden(config.sedeSlug, ordenId)
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
  }, [fase, ordenId, config.sedeSlug]);

  // Motor 'reserva': esperar al webhook. Solo `pagada` es éxito; `cancelada` (cupo lleno, reembolso) es fallo.
  useEffect(() => {
    if (fase !== 'confirmando') return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const consultar = async () => {
      try {
        const estado = await getEstadoReserva(checkoutId, config.empresaSlug);
        if (cancelado) return;
        if (estado.estado === 'pagada') return setFase('exito');
        if (estado.estado === 'cancelada') return setMotivoFallo(''), setFase('fallo');
      } catch {
        // sin red: seguir consultando
      }
      if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
    };
    consultar();
    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [fase, checkoutId, config.empresaSlug]);

  const enviar = useCallback(async () => {
    if (fase === 'enviando' || fase === 'pagando' || fase === 'capturando' || fase === 'confirmando') return;
    setFase('enviando');
    setError('');
    const c = cfg.current;
    try {
      const payload = c.armarPayload(checkoutId);
      if (c.motor === 'orden') {
        const creada = await crearOrden(c.sedeSlug, payload as CrearOrdenInput);
        setOrdenId(creada.orden_id);
        guardar({ checkoutId, ordenId: creada.orden_id });
        const respuesta = await crearPagoOrden(c.sedeSlug, creada.orden_id);
        setPagos(respuesta.map((p) => ({
          empresaSlug: p.empresa_slug, monto: p.monto, clientSecret: p.client_secret, publishableKey: p.publishable_key,
        })));
      } else {
        const reserva = await guardarReserva(
          { ...(payload as ReservaInput), captcha_token: c.captchaToken() }, c.empresaSlug,
        );
        const pago = await crearPago(
          reserva.id,
          { checkout_id: checkoutId, forma_pago: c.formaPago, codigo_promocional: c.codigoPromocional || undefined },
          c.empresaSlug,
        );
        setPagos([{
          empresaSlug: c.empresaSlug, monto: pago.monto_a_cobrar,
          clientSecret: pago.client_secret, publishableKey: pago.publishable_key,
        }]);
      }
      setIndice(0);
      setFase('pagando');
    } catch (err) {
      // Un 503 ("Stripe no configurado") lo traduce `mensajeDeError` a `checkout.paymentUnavailable`.
      setError(c.mensajeDeError(err));
      setFase('formulario');
    }
  }, [fase, checkoutId, guardar]);

  const onPagoConfirmado = useCallback(
    () => {
      if (indice >= pagos.length - 1) {
        // 'orden': hay que capturar todos los pagos autorizados. 'reserva': esperar al webhook.
        setFase(cfg.current.motor === 'orden' ? 'capturando' : 'confirmando');
        return;
      }
      setIndice(indice + 1);
    },
    [indice, pagos.length],
  );

  const onPagoRechazado = useCallback((mensaje: string) => {
    setMotivoFallo(mensaje);
    if (cfg.current.motor === 'orden') {
      // pedir confirmar-captura revierte la orden incompleta (void del primer pago)
      setFase('capturando');
    } else {
      setError(mensaje);
      setFase('formulario');
    }
  }, []);

  const reiniciar = useCallback(() => {
    try {
      window.sessionStorage.removeItem(clave);
    } catch {
      // nada que limpiar
    }
    window.location.reload();
  }, [clave]);

  return {
    fase, pagos, indice, error, motivoFallo, ordenId, checkoutId,
    enviar, onPagoConfirmado, onPagoRechazado, reiniciar,
  };
}
