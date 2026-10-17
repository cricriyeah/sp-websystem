import type { Metadata } from 'next';
import localFont from 'next/font/local';
import '../globals.css';
import { getDictionary, hasLocale } from './dictionaries';
import { notFound } from 'next/navigation';
import { CookieNotice } from '@/components/cookie-notice';
import { LangSwitch } from '@/components/lang-switch';
import { RefCapture } from '@/components/ref-capture';
import { ProveedorToast } from '@/components/toast';
import { MotionProvider } from '@/components/ui/motion-provider';
import { LOCALE_TAG, SITE_URL, absolutaEn, alternativasDe } from '@/lib/site';

// Titulares (display, titulo de pagina, de seccion y de paso): Consola Mono, solo el peso 700
// (Book no se incorpora). Se sirve desde el sitio, recortada a latin con acentos, puntuacion,
// moneda y flechas (src/app/fonts/LICENCIAS.md). El cuerpo y los formularios NO descargan nada:
// usan la pila del sistema de globals.css (`--font-sans`: San Francisco en Apple, Segoe UI en
// Windows, Roboto en Android).
//
// `fallback` es la pila monoespaciada de design.md y `adjustFontFallback: false`: el ajuste
// automatico de Next solo sabe escalar Arial o Times New Roman (proporcionales), y una
// proporcional ajustada al ancho medio no iguala los renglones de una monoespaciada. Consola Mono
// mide 0,586 em por caracter; Menlo, SF Mono y Roboto Mono miden ~0,60 (+2 a 3 %) y Consolas
// ~0,55 (-6 %), asi que el cambio de fuente mueve poco los cortes de renglon.
const consolaMono = localFont({
  src: '../fonts/ConsolaMono-Bold.woff2',
  variable: '--font-titulo',
  weight: '700',
  style: 'normal',
  display: 'swap',
  fallback: ['Consolas', 'SF Mono', 'SFMono-Regular', 'Menlo', 'Roboto Mono', 'ui-monospace', 'monospace'],
  adjustFontFallback: false,
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
      className={consolaMono.variable}
    >
      <body suppressHydrationWarning>
        {/* Un solo juego de funciones de motion para todo el sitio; ver motion-provider.tsx. */}
        <MotionProvider>
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
        </MotionProvider>
      </body>
    </html>
  );
}
