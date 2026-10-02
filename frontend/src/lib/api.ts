const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
// Mismo slug que crea `tenancy.0002_crear_sede_empresa_la_paz` en el backend.
const EMPRESA_SLUG = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

export type Moneda = 'MXN' | 'USD';

export type Zona = 'centro' | 'periferia';

export type PuntoEncuentro = {
  id: number;
  nombre: string;
  zona: Zona;
};

/**
 * @deprecated SP1: El transporte deja de ser personalización/selección en checkout.
 * Lo que el cliente eligio para el traslado, si eligio uno. `null` = sin
 * transporte.
 */
export type TransporteSeleccion = {
  punto_encuentro?: number | null;
  direccion_personalizada?: string;
  zona?: Zona | '';
  // Cuantas personas del grupo usan el transporte. `null`/ausente = todo el
  // grupo. Solo afecta si aplica el recargo de grupo (ver
  // apps/payments/views.py, `_resolver_transporte`) — el precio base no
  // escala por persona.
  cantidad?: number | null;
};

export type MotivoNoDisponible = 'lleno' | 'sin_panga' | 'sin_lugar';

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
  // el dia tiene espacio, pero ya no queda embarcacion donde quepa este grupo.
  // 'sin_lugar' = mismo significado que sin_panga para servicios/hospedaje.
  motivo_no_disponible: MotivoNoDisponible | null;
};

export type Aeropuerto = 'lap' | 'sjd';

export type ReservaInput = {
  // Identificador de la sesion de checkout que genera el navegador. El backend
  // lo usa como llave: mientras la reserva siga pendiente de pago, reenviar el
  // checkout reescribe la misma fila en vez de crear otra.
  checkout_id: string;
  fecha: string;
  // Ausente en un paquete que no pide hora (`pide_hora: false`).
  hora?: string;
  numero_personas: number;
  nombre_cliente: string;
  telefono_cliente: string;
  correo_cliente: string;
  moneda: Moneda;
  // Deslinde de responsabilidad. El servidor sella la fecha/hora y la IP.
  deslinde_aceptado: boolean;
  deslinde_nombre: string;
  // Codigo de la vendedora que trajo al cliente (ver src/lib/ref.ts). El backend
  // ignora en silencio el que no resuelva: un link viejo no puede impedir una
  // reserva.
  ref?: string;
  // Token de Cloudflare Turnstile. El backend solo lo exige al CREAR la reserva
  // — el token es de un solo uso y este endpoint es un upsert, asi que corregir
  // la fecha reenvia sin token (ver backend/apps/bookings/views.py).
  captcha_token?: string;
  // Slug o ID del Paquete de experiencias que ampara esta reserva (si aplica).
  paquete?: string | number | null;
  servicio?: string;
  // Paquete de una sola empresa: personas por id de servicio.
  // `numero_personas` corresponde al componente operativo principal.
  personas_por_servicio?: Record<string, number>;
  // Solo para hospedaje suelto; la salida de un paquete la define el catálogo.
  fecha_salida?: string;
  // Paquete con hospedaje y traslado: aeropuerto del que llega la clienta (el traslado es redondo).
  aeropuerto?: Aeropuerto;
  // Seleccion de personalizaciones (brunch, licencia, carnada, etc.), sin
  // precio: el unico que lo congela es `crear-pago`, con el catalogo vigente
  // en ese momento (ver backend/apps/bookings/serializers.py). Se manda
  // siempre, incluido `[]`, para que reenviar el checkout borre una seleccion
  // vieja en vez de conservarla.
  personalizaciones: { id: number; cantidad?: number; respuesta?: string }[];
};

export type Reserva = ReservaInput & {
  id: number;
  estado: string;
  fecha_inicio_paquete?: string;
};

export type PagoInput = {
  // Acredita que quien pide el cobro es quien abrio este checkout: los ids de
  // reserva son consecutivos y la API es publica.
  checkout_id: string;
  forma_pago: 'completo' | 'anticipo';
  // Solo si el cliente aplico uno en el paso de pago; el descuento real lo
  // calcula y congela crear-pago (ver apps/payments/views.py), nunca el navegador.
  codigo_promocional?: string;
};

export type Pago = {
  client_secret: string;
  publishable_key: string;
  monto_a_cobrar: string;
  precio_total: string;
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

async function request<T>(path: string, init?: RequestInit, empresaSlug?: string): Promise<T> {
  // Cada ruta exportada de este archivo empieza con '/api/' (ver getCupo,
  // etc. mas abajo) — se reescribe aqui, en un solo lugar, en vez de
  // que cada funcion exportada tenga que acordarse del slug.
  // Rutas de plataforma multi-sede (/api/sedes/) no se atan a una empresa.
  const slug = empresaSlug ?? EMPRESA_SLUG;
  const rutaConEmpresa = path.startsWith('/api/sedes')
    ? path
    : path.startsWith('/api/')
    ? `/api/${slug}${path.slice(4)}`
    : path;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${rutaConEmpresa}`, {
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

export const getCupo = (fecha: string, personas: number, empresaSlug?: string) =>
  request<Cupo>(`/api/cupo/?fecha=${fecha}&personas=${personas}`, undefined, empresaSlug);

/** Por que no cabe el grupo cada dia del rango; null = si cabe. */
export type DisponibilidadRango = Record<string, MotivoNoDisponible | null>;

/**
 * Disponibilidad de todo un rango en UNA peticion, para pintar en gris los dias
 * llenos del calendario.
 *
 * No preguntar dia por dia: son 30 peticiones por mes contra un limite de 60/min
 * por IP, y el segundo mes devuelve 429. El backend tampoco pasa de 62 dias por
 * llamada.
 */
export const getCupoRango = (desde: string, hasta: string, personas: number, empresaSlug?: string) =>
  request<{ dias: DisponibilidadRango }>(
    `/api/cupo/rango/?desde=${desde}&hasta=${hasta}&personas=${personas}`,
    undefined,
    empresaSlug,
  ).then((r) => r.dias);

/** Crea la reserva de este checkout, o actualiza la que ya existia. */
export const guardarReserva = (data: ReservaInput, empresaSlug?: string) =>
  request<Reserva>('/api/reservas/', { method: 'POST', body: JSON.stringify(data) }, empresaSlug);

export const crearPago = (reservaId: number, data: PagoInput, empresaSlug?: string) =>
  request<Pago>(`/api/reservas/${reservaId}/crear-pago/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, empresaSlug);

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
  // Solo seleccion, sin precio: eso solo existe desde que se paga (ver
  // apps/payments/views.py, EstadoReservaView). `cantidad` es la que el
  // cliente ya habia elegido (solo importa en items `cantidad_editable`).
  personalizaciones: { id: number; cantidad: number; respuesta: string }[];
  transporte: {
    punto_encuentro: number | null;
    direccion_personalizada: string;
    zona: Zona;
    cantidad: number | null;
  } | null;
  detalle_transporte: {
    tipo_traslado: TipoTraslado;
    punto_encuentro_id: number | null;
    direccion_personalizada: string;
    zona: Zona | '';
    fecha_regreso: string | null;
    numero_personas: number | null;
    precio_calculado: string | null;
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
  personalizaciones: {
    nombre: string;
    tipo_interaccion: string;
    cantidad: number;
    respuesta: string;
    monto: string | null;
  }[];
  transporte: { monto: string; numero_personas: number | null } | null;
  codigo_promocional: string | null;
  descuento_aplicado: string | null;
};

export type EstadoReservaCancelada = { estado: 'cancelada' };

export type EstadoReserva = EstadoReservaPendiente | EstadoReservaPagada | EstadoReservaCancelada;

export const getEstadoReserva = (checkoutId: string, empresaSlug?: string) =>
  request<EstadoReserva>(`/api/reservas/estado/?checkout_id=${checkoutId}`, undefined, empresaSlug);

/**
 * Validacion en vivo de un codigo promocional mientras el cliente lo escribe
 * (ver apps/payments/views.py, ValidarCodigoPromocionalView). Solo informativa:
 * `crear-pago` vuelve a validarlo con el subtotal real antes de congelar el
 * descuento. `valido: false` cubre por igual un codigo que no existe, vencido,
 * agotado o desactivado — nunca distingue el motivo.
 */
export type CodigoPromocionalCheck = { valido: boolean; porcentaje_descuento: string | null };

export const validarCodigoPromocional = (codigo: string, correoCliente: string, empresaSlug?: string) =>
  request<CodigoPromocionalCheck>(
    `/api/codigo-promocional/validar/?codigo=${encodeURIComponent(codigo)}&correo_cliente=${encodeURIComponent(correoCliente)}`,
    undefined,
    empresaSlug,
  );

/* ==========================================================================
   Catálogo Multi-Sede y Paquetes de Experiencias
   ========================================================================== */

export type Sede = {
  id: number;
  nombre: string;
  slug: string;
  zona_horaria: string;
  tipo_cambio_usd: string;
};

export type ServicioPersonalizacionCatalogo = {
  id: number;
  personalizacion_id: number;
  nombre: string;
  tipo: string;
  tipo_interaccion: 'check' | 'input_texto' | 'input_numero' | 'input_seleccion';
  opciones_seleccion: string[];
  aviso_reforzado: boolean;
  cobrar_por_persona: boolean;
  cantidad_editable: boolean;
  precio: string;
  obligatorio: boolean;
  preseleccionado: boolean;
};

export type ServicioCatalogo = {
  id: number;
  empresa_slug: string;
  nombre: string;
  slug: string;
  tipo_servicio: string;
  estrategia_cupo: string;
  estrategia_precio: string;
  modo_ocupacion: string;
  precio_base: string;
  precio_persona_extra: string;
  tipo_cambio_usd: string;
  personas_incluidas: number;
  permite_anticipo: boolean;
  porcentaje_anticipo: number;
  descripcion: string;
  activo: boolean;
  // Rango y paso de las horas de salida que ofrece el servicio (ver lib/horario-servicio.ts).
  pide_hora: boolean;
  hora_apertura: string | null;
  hora_cierre: string | null;
  paso_hora_minutos: number;
  personalizaciones: ServicioPersonalizacionCatalogo[];
};

export type PaqueteServicioCatalogo = {
  id: number;
  servicio_id: number;
  servicio: ServicioCatalogo;
  orden: number;
  dia_estancia: number;
  noches: number | null;
  personas_incluidas: number;
};

export type PaqueteCatalogo = {
  id: number;
  sede: string;
  sede_slug: string;
  empresa_lider: string;
  empresa_lider_slug: string;
  nombre: string;
  slug: string;
  descripcion: string;
  precio_ancla: string;
  tipo_cambio_usd: string;
  estrategia_precio: 'por_grupo' | 'por_persona';
  personas_precio_base: number;
  precio_persona_extra: string;
  precio_depende_de_personas: boolean;
  // false: el paquete no pide hora de salida (la acuerda el capitan durante la estadia).
  pide_hora: boolean;
  regla_precio: string;
  permite_anticipo: boolean; // efectivo: false si el paquete es de dos empresas
  porcentaje_anticipo: number;
  es_cruza_empresa: boolean;
  noches: number | null;
  activo: boolean;
  servicios_asociados: PaqueteServicioCatalogo[];
};

export const getSedes = () =>
  request<Sede[]>('/api/sedes/', { signal: AbortSignal.timeout(8000) });

export const getPaquetesSede = (sedeSlug: string) =>
  request<PaqueteCatalogo[]>(`/api/sedes/${sedeSlug}/paquetes/`);

export const getPaqueteDetalle = (sedeSlug: string, paqueteSlug: string) =>
  request<PaqueteCatalogo>(`/api/sedes/${sedeSlug}/paquetes/${paqueteSlug}/`);

export const getServiciosSede = (sedeSlug: string) =>
  request<ServicioCatalogo[]>(`/api/sedes/${sedeSlug}/servicios/`);

export const getServicioDetalle = (servicioSlug: string, empresaSlug?: string) =>
  request<ServicioCatalogo>(`/api/servicios/${servicioSlug}/`, undefined, empresaSlug);

export { ApiError };

export type TipoTraslado = 'redondo_aeropuerto' | 'redondo_actividad' | 'recepcion_aeropuerto';

export type TrasladosCatalogo = {
  servicio: {
    slug: string;
    nombre: string;
    capacidad_maxima: number | null;
    permite_anticipo: boolean;
    porcentaje_anticipo: number;
    empresa_slug: string;
    hora_apertura: string | null;
    hora_cierre: string | null;
    paso_hora_minutos: number;
  };
  tarifas: {
    tipo_traslado: TipoTraslado;
    zona: Zona | '';
    personas_min: number;
    personas_max: number | null;
    precio: string;
  }[];
  tipo_cambio_usd: string;
  puntos_encuentro: PuntoEncuentro[];
  publishable_key: string;
};

export const getTraslados = (empresaSlug: string): Promise<TrasladosCatalogo> =>
  request<TrasladosCatalogo>('/api/traslados/', undefined, empresaSlug);

export type ReservaTrasladoInput = Pick<ReservaInput,
  | 'checkout_id' | 'fecha' | 'hora' | 'numero_personas'
  | 'nombre_cliente' | 'telefono_cliente' | 'correo_cliente'
  | 'moneda' | 'deslinde_aceptado' | 'deslinde_nombre' | 'ref' | 'captcha_token'
> & {
  servicio: string;
  tipo_traslado: TipoTraslado;
  punto_encuentro?: number | null;
  direccion_personalizada?: string;
  zona?: Zona | '';
  fecha_regreso?: string | null;
  forma_pago: PagoInput['forma_pago'];
};

export type ReservaTraslado = Omit<ReservaTrasladoInput, 'ref' | 'captcha_token'> & {
  id: number;
  estado: string;
};

export const crearReservaTraslado = (empresaSlug: string, payload: ReservaTrasladoInput) =>
  request<ReservaTraslado>('/api/reservas/', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, empresaSlug);

export type ComponenteOrdenInput = {
  servicio: string | number;
  hora?: string;
  numero_personas?: number;
  tipo_traslado?: TipoTraslado;
  punto_encuentro?: number | null;
  direccion_personalizada?: string;
  zona?: Zona | '';
  // Solo si el paquete no incluye hospedaje; con hospedaje la define el paquete.
  fecha_regreso?: string | null;
  personalizaciones?: { id: number; cantidad?: number; respuesta?: string }[];
};

export type CrearOrdenInput = {
  checkout_id?: string;
  paquete: string;
  deslinde_aceptado: boolean;
  deslinde_nombre: string;
  nombre_cliente: string;
  telefono_cliente: string;
  correo_cliente: string;
  moneda?: Moneda;
  ref?: string;
  componentes?: ComponenteOrdenInput[];
  fecha?: string;
  hora?: string;
};

export type OrdenCreada = {
  orden_id: number;
  checkout_id: string | null;
  estado: string;
  reservas: {
    id: number;
    empresa_slug: string;
    servicio: string;
  }[];
};

export const crearOrden = (sedeSlug: string, payload: CrearOrdenInput): Promise<OrdenCreada> =>
  request<OrdenCreada>('/api/ordenes/', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, sedeSlug);

export type PagoOrdenItem = {
  empresa_slug: string;
  monto: string;
  client_secret: string;
  publishable_key: string;
};

export const crearPagoOrden = (sedeSlug: string, ordenId: number): Promise<PagoOrdenItem[]> =>
  request<PagoOrdenItem[]>(`/api/ordenes/${ordenId}/crear-pago/`, {
    method: 'POST',
  }, sedeSlug);

export type ConfirmarCapturaRespuesta = {
  estado: string;
  motivo?: string;
};

export const confirmarCapturaOrden = (sedeSlug: string, ordenId: number): Promise<ConfirmarCapturaRespuesta> =>
  request<ConfirmarCapturaRespuesta>(`/api/ordenes/${ordenId}/confirmar-captura/`, {
    method: 'POST',
  }, sedeSlug);

export type OrdenDetalle = {
  id: number;
  checkout_id: string | null;
  estado: string;
  reservas: {
    reserva_id: number;
    empresa_slug: string;
    servicio: string;
    pago: {
      estado_pi: string | null;
      client_secret: string | null;
      publishable_key: string;
      monto: string | null;
    };
  }[];
};

export const getOrden = (sedeSlug: string, idOCheckoutId: number | string): Promise<OrdenDetalle> => {
  const path = typeof idOCheckoutId === 'number'
    ? `/api/ordenes/${idOCheckoutId}/`
    : `/api/ordenes/?checkout_id=${encodeURIComponent(idOCheckoutId)}`;
  return request<OrdenDetalle>(path, undefined, sedeSlug);
};

export type Situacion =
  | 'sin_pago' | 'pago_en_proceso' | 'retenido_parcial' | 'retenido_total' | 'confirmando_cobro'
  | 'confirmada' | 'cancelada_liberada' | 'cancelada_devolucion_solicitada'
  | 'cancelada_devolucion_por_confirmar' | 'expirada' | 'no_existe';

export type ResumenReserva = {
  situacion: Situacion;
  producto: string;
  monto: string | null;
  moneda: string;
  forma_pago: string;
  folio: number;
  vence_en: null;
};

export type ResumenOrden = {
  situacion: Situacion;
  producto: string;
  moneda: string;
  forma_pago: string;
  montos: {
    empresa: string;
    monto: string | null;
    monto_reembolsado: string | null;
    estado: string | null;
  }[];
  folio: number;
  vence_en: string | null;
  actualizado_en: string;
};

export const getResumenReserva = (checkoutId: string, empresaSlug: string) =>
  request<ResumenReserva>(`/api/reservas/resumen/?checkout_id=${encodeURIComponent(checkoutId)}`, undefined, empresaSlug);

export const getResumenOrden = (checkoutId: string, sedeSlug: string) =>
  request<ResumenOrden>(`/api/ordenes/resumen/?checkout_id=${encodeURIComponent(checkoutId)}`, undefined, sedeSlug);

export const cancelarOrdenPublica = (sedeSlug: string, ordenId: number, checkoutId: string) =>
  request<ResumenOrden>(`/api/ordenes/${ordenId}/cancelar/`, {
    method: 'POST', body: JSON.stringify({ checkout_id: checkoutId }),
  }, sedeSlug);
