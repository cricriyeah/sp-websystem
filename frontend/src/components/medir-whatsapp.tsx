'use client';

import { useEffect } from 'react';
import { esEnlaceWhatsapp, medir } from '@/lib/medicion';

/**
 * Cuenta cada toque a un enlace de WhatsApp del sitio como `Contact` (ver `lib/medicion.ts`). Mucha venta
 * se cierra por WhatsApp: sin esto, el anuncio que la trajo no se entera. Un solo oyente en el documento
 * (montado en el layout) en lugar de tocar cada botón.
 */
export function MedirWhatsapp() {
  useEffect(() => {
    const alTocar = (e: MouseEvent) => {
      const enlace = (e.target as Element | null)?.closest?.('a[href]');
      if (enlace && esEnlaceWhatsapp(enlace.getAttribute('href') ?? '')) medir('Contact');
    };
    document.addEventListener('click', alTocar, { capture: true });
    return () => document.removeEventListener('click', alTocar, { capture: true });
  }, []);
  return null;
}
