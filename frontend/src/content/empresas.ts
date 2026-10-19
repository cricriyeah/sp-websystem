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
      es: 'Pesca deportiva en La Paz con capitanes locales. Salidas privadas desde Marina La Costa.',
      en: 'Sportfishing in La Paz with local captains. Private trips from Marina La Costa.',
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
      es: 'Transporte turístico y privado en La Paz: traslados a aeropuerto y hospedajes, y transporte para eventos.',
      en: 'Tourist and private transport in La Paz: airport and lodging transfers, and transport for events.',
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
      es: 'Pesca con mosca, avistamiento de ballenas y orcas, hospedaje, traslado de aeropuerto y paquetes de varios días.',
      en: 'Fly fishing, whale and orca watching, lodging, airport transfers and multi-day packages.',
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
      es: 'Familia local de Puerto Chale, Baja California Sur: safari marino, avistamiento de ballena gris y pesca deportiva.',
      en: 'A local family in Puerto Chale, Baja California Sur: marine safaris, gray whale watching and sport fishing.',
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
