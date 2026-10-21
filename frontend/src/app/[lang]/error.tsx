'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { botonClases } from '@/components/ui/variantes';
import { textosDeError } from '@/lib/errores-textos';

/**
 * Error de una pagina dentro de /[lang]. No atrapa fallos del layout (p. ej.
 * `getDictionary`): esos caen en `global-error.tsx`. `retry()` vuelve a pedir
 * los datos; `reset()` solo limpiaria el estado sin repedir.
 */
export default function ErrorDePagina({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const { idioma, titulo, cuerpo, reintentar, inicio } = textosDeError(useParams().lang);

  useEffect(() => {
    console.error(error.digest ? `[${error.digest}]` : '', error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col items-center justify-center px-6 text-center sm:px-8">
      <h1 className="texto-pagina">
        {titulo}
      </h1>
      <p className="mt-5 max-w-[46ch] texto-cuerpo">{cuerpo}</p>
      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Button variante="campana" type="button" onClick={() => retry()}>
          {reintentar}
        </Button>
        <Link href={`/${idioma}`} className={botonClases({ variante: 'campana-gris' })}>
          {inicio}
        </Link>
      </div>
    </main>
  );
}
