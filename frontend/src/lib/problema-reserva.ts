// Los problemas de una reserva en curso, en un solo molde: qué ocurrió, qué se conserva,
// qué pasó con el dinero y UNA acción principal. Sin React ni red: los textos llegan
// ya traducidos y `AvisoAccion` solo los pinta.
import type { ClaseDeFallo } from './errores';

export type TipoProblema =
  | 'sin_cupo' | 'tarjeta_rechazada' | 'apartado_vencido' | 'red' | 'catalogo_caido' | 'dato_previo';

export type ClaveAccion = 'elegir_fecha' | 'otra_tarjeta' | 'reapartar' | 'reintentar' | 'whatsapp' | 'volver' | 'corregir';

export type AccionProblema = { clave: ClaveAccion; etiqueta: string };

export type Problema = {
  tipo: TipoProblema;
  queOcurrio: string;
  queSeConserva: string;
  /** Qué pasó con el dinero: va antes que la acción. */
  lineasDinero: string[];
  accionPrincipal: AccionProblema;
  accionSecundaria?: AccionProblema;
  /** Impide seguir: la barra oculta su botón y la acción del aviso es el botón de la pantalla. */
  bloquea: boolean;
  tono: 'aviso' | 'error';
};

export type TextoProblema = { titulo: string; cuerpo: string; accion: string };

export type TextosProblema = Record<Exclude<TipoProblema, 'catalogo_caido'>, TextoProblema> & {
  catalogo_caido: TextoProblema & { whatsapp: string; volver: string };
};

export type ContextoProblema = {
  /** Líneas de dinero ya redactadas (p. ej. la retención de otra empresa). */
  lineasDinero?: string[];
  /** `dato_previo`: el dato y el paso donde se corrige. */
  dato?: string;
  paso?: string;
  /** Hay número de WhatsApp configurado (`lib/contacto`). */
  tieneWhatsapp: boolean;
};

export function tipoDeFallo(clase: ClaseDeFallo): TipoProblema {
  switch (clase) {
    case 'sin_cupo': return 'sin_cupo';
    case 'no_disponible': return 'catalogo_caido';
    default: return 'red';
  }
}

const ACCION_PRINCIPAL: Record<Exclude<TipoProblema, 'catalogo_caido'>, ClaveAccion> = {
  sin_cupo: 'elegir_fecha',
  tarjeta_rechazada: 'otra_tarjeta',
  apartado_vencido: 'reapartar',
  red: 'reintentar',
  dato_previo: 'corregir',
};

const BLOQUEA: Record<TipoProblema, boolean> = {
  sin_cupo: true, tarjeta_rechazada: true, apartado_vencido: true, catalogo_caido: true, red: false, dato_previo: false,
};

const TONO: Record<TipoProblema, 'aviso' | 'error'> = {
  sin_cupo: 'aviso', apartado_vencido: 'aviso', dato_previo: 'aviso',
  tarjeta_rechazada: 'error', red: 'error', catalogo_caido: 'error',
};

const rellenar = (texto: string, contexto: ContextoProblema) =>
  texto.replace('{dato}', contexto.dato ?? '').replace('{paso}', contexto.paso ?? '');

export function problemaDe(tipo: TipoProblema, contexto: ContextoProblema, textos: TextosProblema): Problema {
  const base = textos[tipo];
  const comun = {
    tipo,
    queOcurrio: base.titulo,
    queSeConserva: rellenar(base.cuerpo, contexto),
    lineasDinero: contexto.lineasDinero ?? [],
    bloquea: BLOQUEA[tipo],
    tono: TONO[tipo],
  };
  if (tipo === 'catalogo_caido') {
    const t = textos.catalogo_caido;
    return {
      ...comun,
      accionPrincipal: contexto.tieneWhatsapp
        ? { clave: 'whatsapp', etiqueta: t.whatsapp }
        : { clave: 'reintentar', etiqueta: t.accion },
      accionSecundaria: { clave: 'volver', etiqueta: t.volver },
    };
  }
  return { ...comun, accionPrincipal: { clave: ACCION_PRINCIPAL[tipo], etiqueta: rellenar(base.accion, contexto) } };
}
