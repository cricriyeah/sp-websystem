/** Textos del calendario, ya traducidos (salen de `dict.checkout.calendario`). */
export type TextosCalendario = {
  mesAnterior: string;
  mesSiguiente: string;
  /** «Ese día ya no tiene lugar. Elige otro.» */
  sinLugar: string;
  /** Motivo en el `aria-label` de un día que no se puede reservar. */
  noReservable: string;
  consultando: string;
  errorCupo: string;
  reintentar: string;
  borrar: string;
  manana: string;
  en2: string;
  /** Razón visible de un atajo deshabilitado. */
  antesDelMinimo: string;
  /** «Del {desde} al {hasta} · {noches} noches». */
  anuncioRango: string;
  /** «Ida {desde}, regreso {hasta}». */
  anuncioIdaRegreso: string;
  leyenda: {
    disponible: string;
    sinCupo: string;
    seleccion: string;
    vistaPrevia: string;
    rango: string;
    hoy: string;
  };
};
