// La proyección de la respuesta de la API a lo mínimo que pintan las tarjetas de producto (F10): precio en
// la moneda de la página, color de su tipo, palabra y foto. La comparten la fila de «Qué puedes reservar» y
// la tarjeta de paquete. Solo corre en servidor.
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { getEmpresa } from '@/content/empresas';
import { claveDePaquete, claveDeServicio, imagenDeCatalogo, imagenesDeCatalogo } from '@/content/imagenes-catalogo';
import { baseDeCobro, palabraDePaquete, palabraDeServicio } from '@/lib/etiquetas-catalogo';
import { colorDePaquete, colorDeServicio } from '@/lib/color-actividad';
import { hrefDetalleServicio } from '@/lib/booking-href';
import { hrefDetallePaquete } from '@/lib/routes';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import type { VistaProducto } from '@/components/tarjeta-producto';

/** En `/en` el precio va primero en dólares y debajo, aproximado, en pesos. */
function precioDe(mxn: (moneda: Moneda) => number | null, lang: Locale, moneda: Moneda) {
  const principal: Moneda = lang === 'en' ? 'USD' : moneda;
  const monto = `${formatearPrecio(mxn(principal), principal)} ${principal}`;
  const aprox = principal === 'USD' ? `≈ ${formatearPrecio(mxn('MXN'), 'MXN')} MXN` : undefined;
  return { monto, aprox };
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
    foto: imagenDeCatalogo(clave, lang),
    precio: porRuta
      ? null
      : { ...precioDe((m) => aMoneda(servicio.precio_base, m, servicio.tipo_cambio_usd), lang, moneda), base: base.texto, conDesde: true },
    capacidad: servicio.capacidad_maxima ?? null,
    hrefDetalle: hrefDetalleServicio(servicio, lang, moneda, sedeSlug),
  };
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
    foto: imagenDeCatalogo(clave, lang),
    fotos: imagenesDeCatalogo(clave, lang),
    precio: base
      ? { ...precioDe((m) => calcularPrecioPaquete(paquete, m).precioFinal, lang, moneda), base: base.texto, conDesde: base.conDesde }
      : null,
    capacidad: null,
    hrefDetalle: hrefDetallePaquete(lang, paquete.sede_slug, paquete.slug, moneda),
  };
}
