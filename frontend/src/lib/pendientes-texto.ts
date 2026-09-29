import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { ResumenOrden, ResumenReserva } from './api';

export type RegistroVisual = 'en_curso' | 'con_dinero' | 'informativo';
export type TextoSituacion = {
  registro: RegistroVisual;
  linea1: string;
  linea2: string;
  principal: string;
  secundaria: string | null;
  requiereConfirmacion: boolean;
};

type Textos = Dictionary['continuar'];

function plantilla(texto: string, datos: Record<string, string | number | undefined>): string {
  return Object.entries(datos).reduce(
    (actual, [clave, valor]) => actual.replaceAll(`{${clave}}`, String(valor ?? '')),
    texto,
  );
}

function dinero(monto: string | null, moneda: string, locale: string): string | null {
  if (monto === null || !Number.isFinite(Number(monto))) return null;
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency: moneda }).format(Number(monto));
  } catch {
    return `${monto} ${moneda}`;
  }
}

function horaDeVencimiento(iso: string | null, locale: string): string | null {
  if (!iso || !Number.isFinite(Date.parse(iso))) return null;
  return new Intl.DateTimeFormat(locale, {
    hour: 'numeric', minute: '2-digit', timeZone: 'America/Mazatlan',
  }).format(new Date(iso));
}

function esOrden(resumen: ResumenReserva | ResumenOrden): resumen is ResumenOrden {
  return 'montos' in resumen;
}

export function textoDeSituacion(dict: Textos, resumen: ResumenReserva | ResumenOrden): TextoSituacion {
  const producto = resumen.producto;
  const datos: Record<string, string | number | undefined> = { producto, folio: resumen.folio };
  const montos = esOrden(resumen) ? resumen.montos : [];
  const comprometidos = montos.filter((m) => m.estado === 'requires_capture' || m.estado === 'succeeded');
  const siguiente = montos.find((m) => m.estado !== 'requires_capture' && m.estado !== 'succeeded');
  const montoReserva = esOrden(resumen) ? null : dinero(resumen.monto, resumen.moneda, dict.locale);
  const retenido = comprometidos[0];
  const montoRetenido = retenido ? dinero(retenido.monto, resumen.moneda, dict.locale) : null;
  const montoPendiente = siguiente ? dinero(siguiente.monto, resumen.moneda, dict.locale) : null;
  const montoDevolucion = esOrden(resumen)
    ? dinero(montos.find((m) => m.monto_reembolsado)?.monto_reembolsado
      ?? montos.find((m) => m.monto)?.monto ?? null, resumen.moneda, dict.locale)
    : montoReserva;
  const vence = horaDeVencimiento(resumen.vence_en, dict.locale);
  const resultado = (registro: RegistroVisual, texto: string, principal: string,
    secundaria: string | null = null, requiereConfirmacion = false): TextoSituacion => ({
    registro, linea1: plantilla(texto, datos), linea2: '',
    principal: plantilla(principal, datos), secundaria, requiereConfirmacion,
  });

  switch (resumen.situacion) {
    case 'sin_pago':
      return resultado('en_curso', dict.sinPago, dict.botonContinuar, dict.botonDescartar);
    case 'retenido_parcial': {
      Object.assign(datos, {
        n: comprometidos.length, total: montos.length,
        montoHecho: montoRetenido ?? undefined, empresaHecha: retenido?.empresa,
        montoFalta: montoPendiente ?? undefined, empresaFalta: siguiente?.empresa,
        monto: montoPendiente ?? undefined, vence: vence ?? undefined,
      });
      const texto = montoRetenido && montoPendiente && vence
        ? dict.retenidoParcial : dict.retenidoParcialSinMonto;
      return resultado('con_dinero', texto,
        montoPendiente ? dict.botonPagarPendiente : dict.botonContinuar,
        dict.botonCancelarRetenido, true);
    }
    case 'retenido_total':
    case 'confirmando_cobro': {
      datos.montos = montos.map((m) => dinero(m.monto, resumen.moneda, dict.locale))
        .filter((m): m is string => m !== null).join(' + ');
      return resultado(resumen.situacion === 'retenido_total' ? 'con_dinero' : 'en_curso',
        dict.retenidoTotal, dict.botonVerEstado);
    }
    case 'pago_en_proceso': {
      const monto = montoReserva ?? (montos.length === 1
        ? dinero(montos[0].monto, resumen.moneda, dict.locale) : null);
      datos.monto = monto ?? undefined;
      return resultado('en_curso', monto ? dict.pagoEnProceso : dict.pagoEnProcesoSinMonto,
        dict.botonVerEstado);
    }
    case 'confirmada': {
      if (resumen.forma_pago === 'anticipo') {
        datos.monto = montoReserva ?? dinero(montos[0]?.monto ?? null, resumen.moneda, dict.locale) ?? undefined;
        return resultado('informativo', datos.monto ? dict.confirmadaAnticipo : dict.confirmadaSinMonto,
          dict.botonVerReservacion, dict.botonCerrar);
      }
      datos.cargos = esOrden(resumen)
        ? montos.map((m) => {
          const monto = dinero(m.monto, resumen.moneda, dict.locale);
          return monto ? `${monto} a ${m.empresa}` : null;
        }).filter((m): m is string => m !== null).join(' y ')
        : montoReserva ?? undefined;
      return resultado('informativo', datos.cargos ? dict.confirmada : dict.confirmadaSinMonto,
        dict.botonVerReservacion, dict.botonCerrar);
    }
    case 'cancelada_liberada':
      return resultado('informativo', dict.canceladaLiberada, dict.botonReservarNuevo,
        dict.botonEntendido);
    case 'cancelada_devolucion_solicitada':
      datos.monto = montoDevolucion ?? undefined;
      return resultado('informativo', montoDevolucion ? dict.devolucionSolicitada : dict.devolucionSolicitadaSinMonto,
        dict.botonVerDetalle, dict.botonEntendido);
    case 'cancelada_devolucion_por_confirmar':
      datos.monto = montoDevolucion ?? undefined;
      return resultado('con_dinero', montoDevolucion ? dict.devolucionPorConfirmar : dict.devolucionPorConfirmarSinMonto,
        dict.botonWhatsApp, dict.botonEntendido);
    case 'expirada':
      return resultado('informativo', retenido ? dict.expiradaConRetencion : dict.expiradaSinDinero,
        retenido ? dict.botonReservarNuevo : dict.botonEmpezarNuevo, dict.botonEntendido);
    case 'no_existe':
      return resultado('informativo', dict.noExiste, dict.botonEmpezarNuevo, dict.botonWhatsApp);
  }
}
