/**
 * Consentimiento de cookies y almacenamiento no esencial.
 *
 * Hoy el sitio no carga ninguna herramienta de rastreo, pero va a cargarlas
 * (analitica, pixel de campanas). El aviso se pone desde antes por una razon
 * practica: la decision del cliente tiene que existir ANTES que el script, no
 * despues. Un banner agregado el mismo dia que la analitica deja sin respuesta
 * a todos los que ya visitaron.
 *
 * La regla que hace que esto sirva de algo: **sin respuesta = no**. Mientras el
 * cliente no acepte, nada no esencial debe correr. Todo script nuevo se monta
 * detras de `consentimientoAceptado()`, nunca suelto en el layout.
 *
 * La decision se guarda en localStorage y no en una cookie a proposito: para
 * leer la cookie que dice si se pueden usar cookies primero hay que poner una.
 */
const CLAVE_CONSENTIMIENTO = 'salysol:cookies';

/**
 * Version del aviso. Si algun dia se agregan usos nuevos —un pixel de anuncios
 * donde antes solo habia analitica— se sube este numero y se vuelve a preguntar:
 * un "si" dado sobre otro texto no cubre el uso nuevo.
 */
const VERSION_AVISO = 1;

export type Consentimiento = 'aceptado' | 'rechazado';

type ConsentimientoGuardado = {
  decision: Consentimiento;
  version: number;
  decididoEn: number;
};

/** La decision vigente, o `undefined` si todavia no ha respondido. */
export function leerConsentimiento(): Consentimiento | undefined {
  try {
    const crudo = window.localStorage.getItem(CLAVE_CONSENTIMIENTO);
    if (!crudo) return undefined;

    const { decision, version }: ConsentimientoGuardado = JSON.parse(crudo);
    // Aviso viejo: la respuesta anterior no cubre lo que dice el nuevo.
    if (version !== VERSION_AVISO) return undefined;
    if (decision !== 'aceptado' && decision !== 'rechazado') return undefined;
    return decision;
  } catch {
    return undefined;
  }
}

export function guardarConsentimiento(decision: Consentimiento) {
  try {
    const dato: ConsentimientoGuardado = {
      decision,
      version: VERSION_AVISO,
      decididoEn: Date.now(),
    };
    window.localStorage.setItem(CLAVE_CONSENTIMIENTO, JSON.stringify(dato));
  } catch {
    // Modo privado o almacenamiento lleno. Se le vuelve a preguntar en la
    // siguiente visita; no se asume un "si" que no dio.
  }
}

/**
 * La puerta para todo script no esencial. Devuelve `false` mientras no haya
 * respuesta, que es justo lo que se quiere: el silencio no autoriza nada.
 */
export function consentimientoAceptado(): boolean {
  return leerConsentimiento() === 'aceptado';
}
