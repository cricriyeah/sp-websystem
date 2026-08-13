import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { StructuredData } from '@/components/structured-data';
import { alternativasDe } from '@/lib/site';
import { Hero } from '@/components/hero';
import { AboutSection } from '@/components/about-section';
import { FleetSection } from '@/components/fleet-section';
import { SeasonSection } from '@/components/season-section';
import { IncludedSection } from '@/components/included-section';
import { GallerySection } from '@/components/gallery-section';
import { ReviewsSection } from '@/components/reviews-section';
import { GroupsSection } from '@/components/groups-section';
import { FaqSection } from '@/components/faq-section';
import { SiteFooter } from '@/components/site-footer';
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
  // en que te subes, que se esta pescando, que cuesta y que traer, como se ve,
  // que dicen otros, y hasta el final las dudas sueltas.
  return (
    <main>
      <StructuredData lang={lang} dict={dict} />
      <Hero lang={lang} dict={dict} minDate={minDate} />
      <AboutSection about={dict.about} />
      <FleetSection fleet={dict.fleet} />
      <SeasonSection season={dict.season} />
      <IncludedSection nav={dict.nav} included={dict.included} />
      <GallerySection gallery={dict.gallery} />
      <ReviewsSection nav={dict.nav} reviews={dict.reviews} />
      <GroupsSection nav={dict.nav} groups={dict.groups} />
      <FaqSection faq={dict.faq} />
      <SiteFooter
        lang={lang}
        footer={dict.footer}
        nav={dict.nav}
        bookLabel={dict.booking.submit}
      />
    </main>
  );
}
