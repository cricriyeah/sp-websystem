import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import '../globals.css';
import { getDictionary, hasLocale } from './dictionaries';
import { notFound } from 'next/navigation';
import { CookieNotice } from '@/components/cookie-notice';
import { RefCapture } from '@/components/ref-capture';
import { ProveedorToast } from '@/components/toast';
import { LOCALE_TAG, SITE_URL, absolutaEn, alternativasDe } from '@/lib/site';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
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
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <body suppressHydrationWarning>
        {/* No pinta nada: solo guarda el ?ref= de la vendedora si viene en la URL. */}
        <RefCapture />
        {/* Envuelve todo para que cualquier pantalla pueda avisar sin montar su
            propio sistema: un solo lenguaje visual para todo el feedback. */}
        <ProveedorToast cerrarLabel={dict.feedback.close}>{children}</ProveedorToast>
        {/* Va fuera del proveedor de avisos: no es feedback de una accion del
            cliente, es un tramite que se contesta una vez y no vuelve. */}
        <CookieNotice lang={lang} cookies={dict.cookies} />
      </body>
    </html>
  );
}
