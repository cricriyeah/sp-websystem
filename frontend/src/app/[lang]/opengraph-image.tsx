import { ImageResponse } from 'next/og';
import { getDictionary, hasLocale } from './dictionaries';

export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = 'Sal y Sol Sportfishing';

/**
 * Imagen que se ve al compartir el enlace en WhatsApp, Facebook o iMessage.
 *
 * Se genera con los colores de la marca en vez de usar una foto porque todavia
 * no hay fotografia propia; cuando llegue, se cambia por el archivo real y las
 * medidas ya son las correctas (1200x630).
 */
export default async function Image({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  const dict = await getDictionary(hasLocale(lang) ? lang : 'es');

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: 80,
          background: 'linear-gradient(150deg, #eef8f7 0%, #86d5d6 45%, #1c858c 100%)',
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 999,
              background: '#0b2420',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 32,
            }}
          >
            🐟
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', color: '#0b2420' }}>
            <span style={{ fontSize: 32, fontWeight: 600 }}>{dict.home.title}</span>
            <span style={{ fontSize: 22, color: '#14403a' }}>{dict.nav.location}</span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <span
            style={{
              fontSize: 68,
              lineHeight: 1.1,
              fontWeight: 600,
              color: '#0b2420',
              maxWidth: 900,
            }}
          >
            {dict.hero.headlineStart} {dict.hero.headlineEmphasis} {dict.hero.headlineEnd}
          </span>
          <span style={{ fontSize: 30, color: '#14403a', maxWidth: 860 }}>
            {dict.about.facts.duration.value} · {dict.about.facts.departure.value} ·{' '}
            {dict.about.facts.capacity.value}
          </span>
        </div>
      </div>
    ),
    size
  );
}
