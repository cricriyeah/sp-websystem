const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type Tarifa = {
  precio: string;
};

export type Cupo = {
  fecha: string;
  cupo_maximo: number;
  ocupadas: number;
  disponible: boolean;
};

export type ReservaInput = {
  fecha: string;
  hora: string;
  numero_personas: number;
  nombre_cliente: string;
  telefono_cliente: string;
  correo_cliente: string;
};

export type Reserva = ReservaInput & {
  id: number;
  estado: string;
};

export type PagoInput = {
  amenities: string[];
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

export const getCupo = (fecha: string) => request<Cupo>(`/api/cupo/?fecha=${fecha}`);

export const crearReserva = (data: ReservaInput) =>
  request<Reserva>('/api/reservas/', { method: 'POST', body: JSON.stringify(data) });

export const crearPago = (reservaId: number, data: PagoInput) =>
  request<Pago>(`/api/reservas/${reservaId}/crear-pago/`, {
    method: 'POST',
    body: JSON.stringify(data),
  });

export { ApiError };
