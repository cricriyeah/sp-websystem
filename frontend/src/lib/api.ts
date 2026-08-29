const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Moneda = 'MXN' | 'USD';

// Precios de lista del backend. `precio` es en pesos y los `*_usd` vienen null
// mientras el negocio no fije ese precio en dolares. Todas las cifras llegan de
// aqui a proposito: la web no debe tener ninguna hardcodeada
// (ver backend/apps/payments/pricing.py). Los extras del checkout (brunch,
// licencia, carnada, transporte) ya no viven aqui: vienen de `/api/extras/`,
// ver `getExtras` mas abajo.
export type Tarifa = {
  precio: string;
  precio_usd: string | null;
  /** Cargo por cada persona arriba de `personas_incluidas`. */
  precio_persona_extra: string;
  precio_persona_extra_usd: string | null;
  personas_incluidas: number;
};

/**
 * Catalogo de extras del checkout (`GET /api/extras/?personas=N&moneda=M`).
 *
 * `monto` ya viene resuelto por el servidor para ese `(personas, moneda)` —
 * la web nunca reimplementa si un extra cobra por persona ni el umbral del
 * recargo de transporte, esas reglas viven solo en
 * apps/payments/pricing.py. `null` = sin precio configurado en esa moneda.
 */
export type ExtraCatalogo = {
  id: number;
  tipo: 'brunch' | 'licencia' | 'carnada' | 'otro';
  nombre: string;
  descripcion: string;
  cobrar_por_persona: boolean;
  preseleccionado: boolean;
  monto: string | null;
};

export type Zona = 'centro' | 'periferia';

export type TransportePrecioCatalogo = {
  zona: Zona;
  min_personas_recargo: number;
  monto: string | null;
};

export type PuntoEncuentro = {
  id: number;
  nombre: string;
  zona: Zona;
};

export type CatalogoExtras = {
  extras: ExtraCatalogo[];
  transporte: TransportePrecioCatalogo[];
  puntos_encuentro: PuntoEncuentro[];
};

export const getExtras = (personas: number, moneda: Moneda) =>
  request<CatalogoExtras>(`/api/extras/?personas=${personas}&moneda=${moneda}`);

/**
 * Lo que el cliente eligio para el traslado, si eligio uno. `null` = sin
 * transporte. `zona` solo cuenta cuando se manda `direccion_personalizada`:
 * si viene `punto_encuentro`, el backend la ignora y usa la del hotel elegido
 * (ver apps/bookings/serializers.py, evita que se pague el precio de otra
 * zona mandando una `zona` que no corresponde).
 */
export type TransporteSeleccion = {
  punto_encuentro?: number | null;
  direccion_personalizada?: string;
  zona?: Zona | '';
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
  // Ids de `ExtrasItem` elegidos (brunch, licencia, carnada). Sin precio: el
  // unico que lo congela es `crear-pago`, con el catalogo vigente en ese
  // momento (ver backend/apps/bookings/serializers.py).
  extras?: number[];
  transporte?: TransporteSeleccion | null;
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
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch (causa) {
    // Sin red, `fetch` lanza un TypeError pelado. Se convierte en ApiError con
    // status 0 para que quien llama tenga una sola forma de error que atrapar:
    // antes este caso se colaba como excepcion cruda y terminaba tragado por un
    // `catch {}` vacio, dejando al cliente mirando una pantalla que no reacciona.
    // Los clientes de este sitio reservan desde el wifi de un hotel; esto no es
    // un caso raro.
    throw new ApiError(0, causa instanceof Error ? causa.message : 'network');
  }

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

/**
 * Estado de la reserva de este `checkout_id`, para reponer un checkout tras un
 * refresh o un cierre accidental de la pestana (ver backend/apps/payments/views.py,
 * `EstadoReservaView`). Un 404 es el caso normal de una pestana nueva, sin nada
 * que recuperar — quien llama debe tratarlo como "no hay nada", no como un error.
 */
export type EstadoReservaPendiente = {
  estado: 'pendiente_pago';
  reserva_id: number;
  fecha: string;
  hora: string;
  numero_personas: number;
  nombre_cliente: string;
  telefono_cliente: string;
  correo_cliente: string;
  moneda: Moneda;
  forma_pago: 'completo' | 'anticipo' | '';
  // Solo ids/datos, sin precio: eso solo existe desde que se paga (ver
  // apps/payments/views.py, EstadoReservaView).
  extras: number[];
  transporte: {
    punto_encuentro: number | null;
    direccion_personalizada: string;
    zona: Zona;
  } | null;
};

export type EstadoReservaPagada = {
  estado: 'pagada';
  reserva_id: number;
  fecha: string;
  hora: string;
  numero_personas: number;
  nombre_cliente: string;
  correo_cliente: string;
  moneda: Moneda;
  forma_pago: 'completo' | 'anticipo' | '';
  monto_pagado: string | null;
  precio_total: string | null;
  // Desglose ya congelado al pagar (mismo precio cobrado, no el vigente del
  // catalogo hoy) — ver apps/payments/views.py, EstadoReservaView.
  extras: { nombre: string; cobrar_por_persona: boolean; monto: string | null }[];
  transporte: { monto: string } | null;
};

export type EstadoReservaCancelada = { estado: 'cancelada' };

export type EstadoReserva = EstadoReservaPendiente | EstadoReservaPagada | EstadoReservaCancelada;

export const getEstadoReserva = (checkoutId: string) =>
  request<EstadoReserva>(`/api/reservas/estado/?checkout_id=${checkoutId}`);

export { ApiError };
