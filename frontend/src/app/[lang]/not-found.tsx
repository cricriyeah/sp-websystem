import Link from 'next/link';
import { getDictionary } from './dictionaries';
import { SiteHeader } from '@/components/site-header';

/**
 * 404 dentro del segmento de idioma.
 *
 * `proxy.ts` mete a todo mundo bajo /es o /en, asi que cualquier URL rota acaba
 * aqui. No puede leer `params` (Next no se los pasa a not-found), asi que va en
 * español, que es el idioma por defecto del sitio.
 */
export default async function NotFound() {
  const dict = await getDictionary('es');
  const { notFound: copy } = dict;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang="es" nav={dict.nav} />

      <main className="mx-auto flex max-w-2xl flex-col justify-center px-6 py-24 sm:px-8">
        <p className="text-sm font-medium tracking-wide text-accent uppercase">404</p>
        <h1 className="mt-3 text-3xl leading-[1.15] text-foreground sm:text-4xl">
          {copy.headline}
        </h1>
        <p className="mt-5 max-w-[60ch] text-base leading-relaxed text-muted">{copy.body}</p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/es"
            className="flex items-center justify-center rounded-full bg-foreground px-6 py-3 text-sm font-medium text-surface transition-opacity hover:opacity-90"
          >
            {copy.cta}
          </Link>
          <Link
            href="/es/reservar"
            className="flex items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-foreground transition-transform hover:scale-[1.02]"
          >
            {copy.ctaBook}
          </Link>
        </div>

        {/* Next no le pasa `params` a not-found, asi que la pagina va en el idioma
            por defecto; este enlace saca al visitante en ingles del callejon. */}
        <Link
          href="/en"
          className="mt-8 text-sm text-muted underline underline-offset-2 transition-colors hover:text-foreground"
        >
          Looking for the English site?
        </Link>
      </main>
    </div>
  );
}
