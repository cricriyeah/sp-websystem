// La proyección de la respuesta de la API a lo mínimo que pintan las tarjetas de producto (F10): precio en
// la moneda de la página, color de su tipo, palabra y foto. La comparten la fila de «Qué puedes reservar» y
// la tarjeta de paquete. Solo corre en servidor.
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { getEmpresa } from '@/content/empresas';
import { claveDePaquete, claveDeServicio, imagenDeCatalogo, imagenesDeCatalogo } from '@/content/imagenes-catalogo';
import { descripcionDeCatalogo } from '@/content/descripciones-catalogo';
import { baseDeCobro, palabraDePaquete, palabraDeServicio } from '@/lib/etiquetas-catalogo';
import { colorDePaquete, colorDeServicio } from '@/lib/color-actividad';
import { hrefDetalleServicio } from '@/lib/booking-href';
import { hrefDetallePaquete } from '@/lib/routes';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { formatHour } from '@/lib/dates';
import type { VistaProducto } from '@/components/tarjeta-producto';

/** En `/en` el precio va primero en dólares y debajo, aproximado, en pesos. */
function precioDe(mxn: (moneda: Moneda) => number | null, lang: Locale, moneda: Moneda) {
  const principal: Moneda = lang === 'en' ? 'USD' : moneda;
  const monto = `${formatearPrecio(mxn(principal), principal)} ${principal}`;
  // La otra moneda, aproximada, para quien piensa en la suya: pesos bajo los dólares y dólares bajo los pesos.
  const otra: Moneda = principal === 'USD' ? 'MXN' : 'USD';
  const enOtra = mxn(otra);
  const aprox = enOtra === null ? undefined : `≈ ${formatearPrecio(enOtra, otra)} ${otra}`;
  return { monto, aprox };
}

/** «5:00 - 7:00 am» (o «9:00 am - 1:00 pm»): la ventana de salida, solo si el servicio pide hora. */
function horarioDe(servicio: ServicioCatalogo): string | null {
  if (!servicio.pide_hora || !servicio.hora_apertura || !servicio.hora_cierre) return null;
  const desde = formatHour(servicio.hora_apertura);
  const hasta = formatHour(servicio.hora_cierre);
  return desde.slice(-2) === hasta.slice(-2) ? `${desde.slice(0, -3)} - ${hasta}` : `${desde} - ${hasta}`;
}

export function vistaDeServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda, sedeSlug: string): VistaProducto {
  const clave = claveDeServicio(servicio.empresa_slug, servicio.slug);
  const empresa = getEmpresa(servicio.empresa_slug);
  const base = servicio.tipo_servicio === 'transporte' ? baseDeCobro('por_ruta', lang) : baseDeCobro(servicio.estrategia_precio, lang);
  const porRuta = !base || !base.conDesde;
  return {
    clave,
    nombre: servicio.nombre,
    empresa: empresa?.nombre ?? servicio.empresa_slug,
    color: colorDeServicio(servicio),
    palabra: palabraDeServicio(servicio.tipo_servicio, lang),
    descripcion: descripcionDeCatalogo(clave, lang),
    horario: horarioDe(servicio),
    incluye: (servicio.incluye?.[lang] ?? []).slice(0, 3),
    foto: imagenDeCatalogo(clave, lang),
    precio: porRuta
      ? null
      : { ...precioDe((m) => aMoneda(servicio.precio_base, m, servicio.tipo_cambio_usd), lang, moneda), base: base.texto, conDesde: true },
    capacidad: servicio.capacidad_maxima ?? null,
    hrefDetalle: hrefDetalleServicio(servicio, lang, moneda, sedeSlug),
  };
}

// Un renglón de «incluye» que en realidad dice lo que NO incluye: no lleva palomita; queda para el detalle.
const EXCLUSION = /no incluye|not include/i;

/** Los renglones de «incluye» de la tarjeta de un paquete: 4 (3 en el teléfono, lo esconde quien pinta); la lista
 * completa está en el detalle. La comparten la sección de paquetes y «Reserva ahora mismo». */
export function incluyeDePaquete(paquete: PaqueteCatalogo, lang: Locale): string[] {
  return (paquete.incluye?.[lang] ?? []).filter((r) => !EXCLUSION.test(r)).slice(0, 4);
}

export function vistaDePaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): VistaProducto {
  const clave = claveDePaquete(paquete.slug);
  const empresa = getEmpresa(paquete.empresa_lider_slug);
  const base = baseDeCobro(paquete.estrategia_precio, lang);
  return {
    clave,
    nombre: paquete.nombre,
    empresa: empresa?.nombre ?? paquete.empresa_lider,
    color: colorDePaquete(paquete),
    palabra: palabraDePaquete(paquete.noches, lang),
    // La del backoffice (ya en el idioma de la página); un texto propio del sitio, si lo hay, manda.
    descripcion: descripcionDeCatalogo(clave, lang) ?? (paquete.descripcion?.trim() || null),
    incluye: incluyeDePaquete(paquete, lang),
    incluyeSiempre: true,
    foto: imagenDeCatalogo(clave, lang),
    fotos: imagenesDeCatalogo(clave, lang),
    precio: base
      ? { ...precioDe((m) => calcularPrecioPaquete(paquete, m).precioFinal, lang, moneda), base: base.texto, conDesde: base.conDesde }
      : null,
    capacidad: null,
    hrefDetalle: hrefDetallePaquete(lang, paquete.sede_slug, paquete.slug, moneda),
  };
}
