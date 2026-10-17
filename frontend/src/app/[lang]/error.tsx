'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
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
      <h1
        className="font-display text-3xl leading-tight text-foreground sm:text-4xl"
        style={{ letterSpacing: 'var(--tracking-titulo)' }}
      >
        {titulo}
      </h1>
      <p className="mt-5 max-w-[46ch] text-base leading-relaxed text-muted">{cuerpo}</p>
      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Button
          variante="libre"
          type="button"
          onClick={() => retry()}
          className="flex items-center justify-center rounded-full bg-action px-7 py-3.5 text-sm font-semibold text-action-foreground transition-transform hover:scale-[1.02] active:scale-[0.98]"
        >
          {reintentar}
        </Button>
        <Link
          href={`/${idioma}`}
          className="flex items-center justify-center rounded-full border border-border-strong px-7 py-3.5 text-sm font-medium text-foreground transition-colors hover:border-foreground"
        >
          {inicio}
        </Link>
      </div>
    </main>
  );
}
