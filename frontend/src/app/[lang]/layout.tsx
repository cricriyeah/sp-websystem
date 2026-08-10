import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import '../globals.css';
import { hasLocale } from './dictionaries';
import { notFound } from 'next/navigation';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Tours de pesca deportiva',
  description: 'Sistema de reservas de tours de pesca deportiva.',
};

export async function generateStaticParams() {
  return [{ lang: 'es' }, { lang: 'en' }];
}

export default async function RootLayout({ children, params }: LayoutProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  return (
    <html
      lang={lang}
      data-scroll-behavior="smooth"
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
