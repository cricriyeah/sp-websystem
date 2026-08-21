const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Moneda = 'MXN' | 'USD';

/** Extras que se piden pero NO se cobran en linea: los cotiza el agente. */
export type SolicitudKey = 'drinks' | 'transport';

// Precios de lista del backend. `precio` es en pesos y los `*_usd` vienen null
// mientras el negocio no fije ese precio en dolares. Todas las cifras llegan de
// aqui a proposito: la web no debe tener ninguna hardcodeada
// (ver backend/apps/payments/pricing.py).
export type Tarifa = {
  precio: string;
  precio_usd: string | null;
  /** Cargo por cada persona arriba de `personas_incluidas`. */
  precio_persona_extra: string;
  precio_persona_extra_usd: string | null;
  personas_incluidas: number;
  /** Precio del lunch POR PERSONA. */
  precio_lunch: string;
  precio_lunch_usd: string | null;
};

export type Cupo = {
  fecha: string;
  cupo_maximo: number;
  ocupadas: number;
  disponible: boolean;
  // Primera fecha con espacio PARA ESE GRUPO a partir de la pedida, o null si no
  // hay ninguna en los proximos 90 dias. La calcula el backend en cuatro
  // consultas: antes el navegador la buscaba preguntando dia por dia, hasta 90
  // peticiones seguidas que agotaban el limite de 60/min y morian en un 429
  // silencioso.
  proxima_disponible: string | null;
  // Por que no se puede. 'lleno' = se acabaron los viajes del dia. 'sin_panga' =
  // el dia tiene espacio, pero ya no queda embarcacion donde quepa este grupo:
  // solo dos de la flota llevan mas de 3 personas.
  motivo_no_disponible: 'lleno' | 'sin_panga' | null;
};

export type ReservaInput = {
  // Identificador de la sesion de checkout que genera el navegador. El backend
  // lo usa como llave: mientras la reserva siga pendiente de pago, reenviar el
  // checkout reescribe la misma fila en vez de crear otra.
  checkout_id: string;
  fecha: string;
  hora: string;
  numero_personas: number;
  nombre_cliente: string;
  telefono_cliente: string;
  correo_cliente: string;
  moneda: Moneda;
  // Deslinde de responsabilidad. El servidor sella la fecha/hora y la IP.
  deslinde_aceptado: boolean;
  deslinde_nombre: string;
  // Extras. El lunch se cobra (por persona); bebidas y transporte quedan como
  // solicitud para que el agente las cotice.
  lleva_lunch: boolean;
  pide_bebidas: boolean;
  pide_transporte: boolean;
  // Codigo de la vendedora que trajo al cliente (ver src/lib/ref.ts). El backend
  // ignora en silencio el que no resuelva: un link viejo no puede impedir una
  // reserva.
  ref?: string;
  // Token de Cloudflare Turnstile. El backend solo lo exige al CREAR la reserva
  // — el token es de un solo uso y este endpoint es un upsert, asi que corregir
  // la fecha reenvia sin token (ver backend/apps/bookings/views.py).
  captcha_token?: string;
};

export type Reserva = ReservaInput & {
  id: number;
  estado: string;
};

export type PagoInput = {
  // Acredita que quien pide el cobro es quien abrio este checkout: los ids de
  // reserva son consecutivos y la API es publica.
  checkout_id: string;
  forma_pago: 'completo' | 'anticipo';
};

export type Pago = {
  client_secret: string;
  publishable_key: string;
  monto_a_cobrar: string;
  moneda: string;
};

class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body ?? res.statusText);
  return body as T;
}

export const getTarifa = () => request<Tarifa>('/api/tarifa/');

export const getCupo = (fecha: string, personas: number) =>
  request<Cupo>(`/api/cupo/?fecha=${fecha}&personas=${personas}`);

/** Por que no cabe el grupo cada dia del rango; null = si cabe. */
export type MotivoNoDisponible = 'lleno' | 'sin_panga';
export type DisponibilidadRango = Record<string, MotivoNoDisponible | null>;

/**
 * Disponibilidad de todo un rango en UNA peticion, para pintar en gris los dias
 * llenos del calendario.
 *
 * No preguntar dia por dia: son 30 peticiones por mes contra un limite de 60/min
 * por IP, y el segundo mes devuelve 429. El backend tampoco pasa de 62 dias por
 * llamada.
 */
export const getCupoRango = (desde: string, hasta: string, personas: number) =>
  request<{ dias: DisponibilidadRango }>(
    `/api/cupo/rango/?desde=${desde}&hasta=${hasta}&personas=${personas}`,
  ).then((r) => r.dias);

/** Crea la reserva de este checkout, o actualiza la que ya existia. */
export const guardarReserva = (data: ReservaInput) =>
  request<Reserva>('/api/reservas/', { method: 'POST', body: JSON.stringify(data) });

export const crearPago = (reservaId: number, data: PagoInput) =>
  request<Pago>(`/api/reservas/${reservaId}/crear-pago/`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export { ApiError };
