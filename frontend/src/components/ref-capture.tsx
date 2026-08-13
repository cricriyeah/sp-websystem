'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { capturarRef } from '@/lib/ref';

/**
 * Guarda el codigo de la vendedora que venga en la URL (`?ref=`), en cualquier
 * pagina del sitio. Va montado en el layout: el link puede caer en la portada y
 * el cliente llegar al checkout tres clics despues, cuando el parametro ya se
 * perdio.
 *
 * Lee `window.location.search` y no `useSearchParams()` a proposito: ese hook
 * saca de la pre-renderizacion estatica a toda pagina que lo use, y aqui no hay
 * nada que renderizar — solo se escribe en localStorage.
 */
export function RefCapture() {
  const pathname = usePathname();

  useEffect(() => {
    capturarRef(window.location.search);
  }, [pathname]);

  return null;
}
