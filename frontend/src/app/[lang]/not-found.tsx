import Link from 'next/link';
import { getDictionary } from './dictionaries';
import { SiteHeader } from '@/components/site-header';

/**
 * 404 dentro del segmento de idioma.
 *
 * No puede leer `params` (Next no se los pasa a not-found), asi que va en
 * español, el idioma por defecto del sitio.
 */
export default async function NotFound() {
  const dict = await getDictionary('es');
  const { notFound: copy } = dict;

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader lang="es" nav={dict.nav} />

      <main
        className="mx-auto flex min-h-dvh max-w-2xl flex-col items-center justify-center px-6 pb-24 text-center sm:px-8"
        style={{ paddingTop: 'calc(2rem + var(--nav-alto))' }}
      >
        <p
          aria-hidden="true"
          className="font-display font-normal leading-none select-none"
          style={{
            fontSize: 'clamp(7rem, 18vw, 14rem)',
            letterSpacing: 'var(--tracking-titulo)',
            color: 'var(--indigo)',
          }}
        >
          404
        </p>

        <h1
          className="mt-4 font-display text-3xl font-normal leading-tight text-foreground sm:text-4xl"
          style={{ letterSpacing: 'var(--tracking-titulo)' }}
        >
          {copy.headline}
        </h1>

        <p className="mt-5 max-w-[46ch] text-base leading-relaxed text-muted">
          {copy.body}
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/es/reservar"
            className="flex items-center justify-center rounded-full px-7 py-3.5 text-sm font-semibold transition-transform hover:scale-[1.02] active:scale-[0.98]"
            style={{ background: 'var(--action)', color: 'var(--ink)' }}
          >
            {copy.ctaBook}
          </Link>

          <Link
            href="/es"
            className="flex items-center justify-center rounded-full border px-7 py-3.5 text-sm font-medium text-foreground transition-colors hover:bg-surface"
            style={{ borderColor: 'var(--border-strong)' }}
          >
            {copy.cta}
          </Link>
        </div>

        <Link
          href="/en"
          className="mt-10 text-xs text-muted underline underline-offset-4 transition-colors hover:text-foreground"
        >
          Looking for the English site?
        </Link>
      </main>
    </div>
  );
}
