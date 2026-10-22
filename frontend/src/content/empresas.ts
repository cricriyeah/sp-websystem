import 'server-only';
import { MARCAS, type MarcaEmpresa } from './empresas-marca';

// Todo lo de cada empresa, en un solo lugar (Task 9.0): la sede, la descripción, el sitio y
// las redes, el contacto confirmado, las reseñas y las fotos. Nombre y logo vienen de
// `empresas-marca.ts` (los usan componentes de cliente). Al ser `server-only`, lo lee siempre
// un `page.tsx` o un Server Component, que pasa por prop solo lo que la vista necesita.
//
// Fuente: `docs/marketing/contenido-empresas.md`. Quedan fuera hasta que la empresa los
// confirme: el WhatsApp de Piratas (+52 612 123 4567, de relleno), sus enlaces de privacidad y
// términos (van a `#`), las reseñas de plantilla (la de La Ventana de 2018, las 5 de DLS) y las
// fotos de Pexels o Unsplash.

type Texto = { es: string; en: string };

export type Resena = {
  autor: string;
  texto: string;
  fuente: { nombre: string; url: string };
  fecha: string;
  idioma: 'es' | 'en';
  /** Solo se muestra con `true`: cada empresa confirma la suya (decisión del dueño). */
  confirmada: boolean;
};

export type Empresa = MarcaEmpresa & {
  sede: string;
  descripcion: Texto;
  /** Su sitio oficial. Sal y Sol no lleva: su sitio es este. */
  web?: string;
  /** El sitio está al día y se enlaza (decisión del dueño, 2026-10-16). */
  webConfirmada: boolean;
  /** Nombre comercial de su sitio cuando difiere del catálogo. */
  tambienConocidaComo?: string;
  redes: { nombre: string; url: string }[];
  /**
   * Teléfono o WhatsApp confirmado, para mostrarlo en la fila de esa empresa. El botón
   * «Escribirnos por WhatsApp» del sitio usa el número único de `lib/contacto.ts`, no este.
   */
  contacto?: { tipo: 'whatsapp' | 'telefono'; numero: string };
  resenas: Resena[];
  /** `propia`: la empresa es dueña de la foto (las de banco no entran). */
  fotos: { src: string; alt: Texto; propia: boolean }[];
};

const marca = (slug: string): MarcaEmpresa => {
  const encontrada = MARCAS.find((m) => m.slug === slug);
  if (!encontrada) throw new Error(`Sin marca para ${slug}`);
  return encontrada;
};

export const EMPRESAS: readonly Empresa[] = [
  {
    ...marca('sal-y-sol'),
    sede: 'la-paz',
    descripcion: {
      es: 'Pesca deportiva en La Paz con capitanes locales. La panga es solo para tu grupo y sale de Marina La Costa al amanecer.',
      en: 'Sportfishing in La Paz with local captains. The panga is just for your group and leaves Marina La Costa at dawn.',
    },
    webConfirmada: false,
    redes: [],
    resenas: [],
    fotos: [],
  },
  {
    ...marca('transporte-la-paz'),
    sede: 'la-paz',
    descripcion: {
      es: 'Traslados privados en La Paz: del aeropuerto a tu hospedaje, a tu actividad y de regreso. También transporte para eventos.',
      en: 'Private transfers in La Paz: from the airport to your lodging, to your activity and back. Event transport too.',
    },
    web: 'https://www.juanviajes.com/',
    webConfirmada: true,
    tambienConocidaComo: 'DLS Tours y Transporte Turístico',
    redes: [
      { nombre: 'Instagram', url: 'https://www.instagram.com/dls.tours/' },
      { nombre: 'Facebook', url: 'https://www.facebook.com/share/16usKfCtQE/?mibextid=wwXIfr' },
    ],
    contacto: { tipo: 'whatsapp', numero: '+52 612 291 4811' },
    resenas: [],
    fotos: [],
  },
  {
    ...marca('la-ventana-travel'),
    sede: 'la-ventana',
    descripcion: {
      es: 'Pesca con mosca, salidas a buscar ballenas y orcas, hospedaje en el Hotel Casa Arrecife y paquetes de varios días con traslado de aeropuerto.',
      en: 'Fly fishing, trips out to find whales and orcas, lodging at Hotel Casa Arrecife and multi-day packages with airport transfers.',
    },
    web: 'https://laventanatravel.com/',
    webConfirmada: true,
    tambienConocidaComo: 'La Ventana Adventures',
    redes: [{ nombre: 'Instagram', url: 'https://www.instagram.com/laventana.travel' }],
    contacto: { tipo: 'whatsapp', numero: '+52 612 179 4239' },
    resenas: [],
    fotos: [],
  },
  {
    ...marca('piratas-adventures'),
    sede: 'puerto-chale',
    descripcion: {
      es: 'Una familia local de Puerto Chale: safari marino, avistamiento de ballena gris y pesca deportiva en el Pacífico.',
      en: 'A local family in Puerto Chale: marine safaris, gray whale watching and sportfishing on the Pacific.',
    },
    web: 'https://piratas-landing.vercel.app/',
    webConfirmada: true,
    redes: [],
    resenas: [],
    fotos: [],
  },
];

export function getEmpresa(slug: string | null | undefined): Empresa | undefined {
  return slug ? EMPRESAS.find((empresa) => empresa.slug === slug) : undefined;
}
