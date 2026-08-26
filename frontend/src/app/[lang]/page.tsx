import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { StructuredData } from '@/components/structured-data';
import { alternativasDe } from '@/lib/site';
import { SiteHeader } from '@/components/site-header';
import { Hero } from '@/components/hero';
import { AboutSection } from '@/components/about-section';
import { SeasonSection } from '@/components/season-section';
import { IncludedSection } from '@/components/included-section';
import { LicenseSection } from '@/components/license-section';
import { GallerySection } from '@/components/gallery-section';
import { ReviewsSection } from '@/components/reviews-section';
import { FaqSection } from '@/components/faq-section';
import { SiteFooter } from '@/components/site-footer';
import { StickyBookingBar } from '@/components/sticky-booking-bar';
import { ProveedorReserva } from '@/components/booking-state';
import { getMinBookableDate } from '@/lib/dates';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);
  return {
    // `absolute` porque la portada ya trae la marca en su titulo; sin esto la
    // plantilla del layout la repetiria.
    title: { absolute: dict.meta.home.title },
    description: dict.meta.home.description,
    alternates: alternativasDe(lang),
  };
}

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const minDate = getMinBookableDate();

  // Orden pensado como la conversacion que tendrias en el muelle: quienes somos,
  // que se esta pescando, que trae el viaje y que llevas tu, el unico tramite
  // que tienes que hacer antes (la licencia), como se ve, que dicen otros, y
  // hasta el final las dudas sueltas.
  return (
    <>
      <StructuredData lang={lang} dict={dict} />
      {/* Fuera del `<main>` y arriba del Hero: la barra es `sticky` y solo se
          queda pegada mientras su contenedor sigue a la vista. Vivio dentro del
          Hero y por eso se iba con la portada al bajar. */}
      <SiteHeader lang={lang} nav={dict.nav} />
      {/* Envuelve el Hero y la barra pegada: las dos barras de reserva de la
          portada comparten las respuestas, no una copia cada una. */}
      <ProveedorReserva>
        <main>
          <Hero lang={lang} dict={dict} minDate={minDate} />
          <AboutSection about={dict.about} />
          <SeasonSection season={dict.season} />
          <IncludedSection included={dict.included} />
          <LicenseSection nav={dict.nav} license={dict.license} />
          <GallerySection gallery={dict.gallery} />
          <ReviewsSection nav={dict.nav} reviews={dict.reviews} />
          <FaqSection faq={dict.faq} />
        </main>
        <SiteFooter
          lang={lang}
          footer={dict.footer}
          nav={dict.nav}
          bookLabel={dict.booking.submit}
        />
        {/* Fuera del `<main>` y al final: es una capa fija sobre la pagina, no
          parte del contenido, y asi ningun `z-index` de seccion la tapa. */}
        <StickyBookingBar lang={lang} booking={dict.booking} minDate={minDate} />
      </ProveedorReserva>
    </>
  );
}
