import type { Metadata } from 'next';
import { Instrument_Sans } from 'next/font/google';
import localFont from 'next/font/local';
import '../globals.css';
import { getDictionary, hasLocale } from './dictionaries';
import { notFound } from 'next/navigation';
import { CookieNotice } from '@/components/cookie-notice';
import { LangSwitch } from '@/components/lang-switch';
import { RefCapture } from '@/components/ref-capture';
import { ProveedorToast } from '@/components/toast';
import { LOCALE_TAG, SITE_URL, absolutaEn, alternativasDe } from '@/lib/site';

// Cuerpo, cifras y toda la interfaz de reserva.
const instrumentSans = Instrument_Sans({
  variable: '--font-cuerpo',
  subsets: ['latin'],
});

// Titulares. Bebas Neue trae un solo peso y **solo caja alta** —sus minusculas
// son las mismas mayusculas—, asi que todo titular sale en versales quiera o no.
// La jerarquia la hace el tamano. globals.css le pone `font-synthesis: none`
// para que ningun navegador finja una negrita que la fuente no tiene, y el
// espaciado positivo que las versales necesitan para no amontonarse.
const bebasNeue = localFont({
  src: '../fonts/BebasNeue-Regular.woff2',
  variable: '--font-titulo',
  weight: '400',
  style: 'normal',
  display: 'swap',
});

// Palabras sueltas de acento dentro de un titular. Ojo: la licencia instalada
// es «personal use only», ver src/app/fonts/LICENCIAS.md antes de lanzar.
const bellaFashion = localFont({
  src: '../fonts/BellaFashion-Regular.woff2',
  variable: '--font-acento',
  weight: '400',
  style: 'normal',
  display: 'swap',
});

export async function generateMetadata({ params }: LayoutProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);

  return {
    // metadataBase vuelve absolutas las rutas de imagenes: las redes sociales no
    // resuelven relativas y la miniatura saldria vacia.
    metadataBase: new URL(SITE_URL),
    title: {
      default: dict.meta.home.title,
      // Las paginas internas solo ponen su nombre; la marca se agrega aqui.
      template: `%s — ${dict.home.title}`,
    },
    description: dict.meta.home.description,
    alternates: alternativasDe(lang),
    openGraph: {
      type: 'website',
      siteName: dict.home.title,
      locale: LOCALE_TAG[lang],
      url: absolutaEn(lang),
      title: dict.meta.home.title,
      description: dict.meta.home.description,
    },
    twitter: {
      card: 'summary_large_image',
      title: dict.meta.home.title,
      description: dict.meta.home.description,
    },
  };
}

export async function generateStaticParams() {
  return [{ lang: 'es' }, { lang: 'en' }];
}

export default async function RootLayout({ children, params }: LayoutProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);

  return (
    <html
      lang={lang}
      data-scroll-behavior="smooth"
      className={`${instrumentSans.variable} ${bebasNeue.variable} ${bellaFashion.variable}`}
    >
      <body suppressHydrationWarning>
        {/* No pinta nada: solo guarda el ?ref= de la vendedora si viene en la URL. */}
        <RefCapture />
        {/* Envuelve todo para que cualquier pantalla pueda avisar sin montar su
            propio sistema: un solo lenguaje visual para todo el feedback. */}
        <ProveedorToast cerrarLabel={dict.feedback.close}>{children}</ProveedorToast>
        {/* Selector de idioma fijo en esquina inferior izquierda para escritorio (en movil vive en el menu) */}
        <div className="fixed bottom-6 left-6 z-40 hidden lg:block print:hidden">
          <LangSwitch lang={lang} label={dict.nav.switchLang} placement="top" align="left" />
        </div>
        {/* Va fuera del proveedor de avisos: no es feedback de una accion del
            cliente, es un tramite que se contesta una vez y no vuelve. */}
        <CookieNotice lang={lang} cookies={dict.cookies} />
      </body>
    </html>
  );
}
