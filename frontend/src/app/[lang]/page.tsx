import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { Hero } from '@/components/hero';
import { AboutSection } from '@/components/about-section';
import { FaqSection } from '@/components/faq-section';
import { SiteFooter } from '@/components/site-footer';

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const minDate = new Date().toISOString().slice(0, 10);

  return (
    <main>
      <Hero lang={lang} dict={dict} minDate={minDate} />
      <AboutSection about={dict.about} />
      <FaqSection faq={dict.faq} />
      <SiteFooter footer={dict.footer} nav={dict.nav} bookLabel={dict.booking.submit} />
    </main>
  );
}
