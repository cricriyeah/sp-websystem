// frontend/src/lib/booking-href.ts
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { esPaqueteCruzaEmpresa } from './pricing-paquete';

export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string {
  const sedeParam = paquete.sede_slug ? `&sede=${paquete.sede_slug}` : '';
  const empresaParam = paquete.empresa_lider_slug
    ? `&paquete_empresa=${paquete.empresa_lider_slug}`
    : '';
  const cruzaEmpresa = esPaqueteCruzaEmpresa(paquete);
  return cruzaEmpresa
    ? `/${lang}/reservar-paquete?paquete=${paquete.slug}${sedeParam}&moneda=${moneda}`
    : `/${lang}/reservar?paquete=${paquete.slug}${sedeParam}${empresaParam}&moneda=${moneda}`;
}

export function hrefServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda): string {
  return `/${lang}/reservar?servicio=${servicio.slug}&empresa=${servicio.empresa_slug}&moneda=${moneda}`;
}
