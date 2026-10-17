'use client';

import { useEffect } from 'react';
import { textosDeError } from '@/lib/errores-textos';

/**
 * Ultimo recurso: atrapa fallos del layout raiz ([lang]/layout.tsx). Reemplaza
 * el documento entero, asi que lleva su propio <html>/<body> y no tiene estilos
 * globales: usa colores del sistema (sin literales) y el idioma del navegador.
 */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const idioma = typeof navigator !== 'undefined' && navigator.language.startsWith('en') ? 'en' : 'es';
  const { titulo, cuerpo, reintentar, inicio } = textosDeError(idioma);

  useEffect(() => {
    console.error(error.digest ? `[${error.digest}]` : '', error);
  }, [error]);

  return (
    <html lang={idioma}>
      <body
        style={{
          margin: 0,
          minHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          padding: '1.5rem',
          textAlign: 'center',
          fontFamily: 'system-ui, sans-serif',
          background: 'Canvas',
          color: 'CanvasText',
        }}
      >
        <h1 style={{ margin: 0, fontSize: '1.875rem' }}>{titulo}</h1>
        <p style={{ margin: 0, maxWidth: '46ch', lineHeight: 1.6 }}>{cuerpo}</p>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button type="button" onClick={() => retry()} style={{ padding: '0.875rem 1.75rem', borderRadius: 9999, cursor: 'pointer' }}>
            {reintentar}
          </button>
          <a href={`/${idioma}`} style={{ padding: '0.875rem 1.75rem', color: 'inherit' }}>
            {inicio}
          </a>
        </div>
      </body>
    </html>
  );
}
