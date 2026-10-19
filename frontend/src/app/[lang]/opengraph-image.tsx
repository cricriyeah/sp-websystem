import { ImageResponse } from 'next/og';
import { getDictionary, hasLocale } from './dictionaries';

export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const alt = 'Sun Baja Experience';

/**
 * Imagen que se ve al compartir el enlace en WhatsApp, Facebook o iMessage.
 *
 * Marca de design.md, plana y sin emoji: pagina en arena, tinta para el texto, un circulo cafe
 * que repite la forma redonda del logo (el logo definitivo no ha llegado: cuando llegue se
 * cambia el circulo por el archivo) y los tres colores de actividad como cuenta de lo que se
 * ofrece (mar, ciudad, outside). Sin fotografia ni degradados. ImageResponse no lee CSS ni las
 * variables de globals.css, por eso los hex van en concreto (el archivo esta en EXENTOS de la
 * regla color-literal de la guardia) y la fuente es la de ImageResponse, no Consola Mono: Satori
 * no lee WOFF2. Las medidas ya son las correctas (1200x630).
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
          background: '#F8F8F6', // arena
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ width: 64, height: 64, borderRadius: 999, background: '#7C3B02' }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 32, fontWeight: 700, color: '#1F1A14' }}>{dict.home.title}</span>
            <span style={{ fontSize: 22, color: '#4A3F33' }}>{dict.hubContenido.og.lugar}</span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <span
            style={{
              fontSize: 68,
              lineHeight: 1.1,
              fontWeight: 700,
              color: '#1F1A14', // tinta
              maxWidth: 900,
            }}
          >
            {dict.hubContenido.og.titular}
          </span>
          <span style={{ fontSize: 30, color: '#6B5D4D', maxWidth: 860 }}>{dict.hubContenido.subtexto}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 56, height: 12, borderRadius: 999, background: '#1B607F' }} />
            <div style={{ width: 56, height: 12, borderRadius: 999, background: '#F64A25' }} />
            <div style={{ width: 56, height: 12, borderRadius: 999, background: '#343F04' }} />
          </div>
        </div>
      </div>
    ),
    size
  );
}
