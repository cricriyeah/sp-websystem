// La proyección de una empresa a lo mínimo que pinta `TarjetaEmpresa` (F10): la comparten el tablero del hub y
// el «Quién opera» de los detalles. Solo corre en servidor.
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Empresa } from '@/content/empresas';
import type { VistaEmpresa } from '@/components/tarjeta-empresa';

export function vistaDeEmpresa(empresa: Empresa, lang: Locale, sedes: VistaEmpresa['sedes']): VistaEmpresa {
  return {
    slug: empresa.slug,
    nombre: empresa.nombre,
    logo: empresa.logo,
    logoLibre: empresa.logoLibre,
    campo: empresa.campo,
    sedes,
    tambienConocidaComo: empresa.tambienConocidaComo,
    descripcion: empresa.descripcion[lang],
    redes: empresa.redes.filter((red) => /instagram|facebook/i.test(red.nombre)),
    // El sitio externo solo si el dueño confirmó que está al día.
    web: empresa.webConfirmada ? empresa.web : undefined,
    contacto: empresa.contacto,
  };
}
