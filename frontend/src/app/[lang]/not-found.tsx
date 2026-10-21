import Link from 'next/link';
import { getDictionary } from './dictionaries';
import { SiteHeader } from '@/components/site-header';
import { botonClases } from '@/components/ui/variantes';

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
      <SiteHeader lang="es" nav={dict.nav} continuar={dict.continuar} variante="sede" />

      <main
        className="mx-auto flex min-h-dvh max-w-2xl flex-col items-center justify-center px-6 pb-24 text-center sm:px-8"
        style={{ paddingTop: 'calc(2rem + var(--nav-alto))' }}
      >
        <p aria-hidden="true" className="texto-gigante select-none text-coral">
          404
        </p>

        <h1 className="mt-4 texto-pagina">
          {copy.headline}
        </h1>

        <p className="mt-5 max-w-[46ch] texto-cuerpo">
          {copy.body}
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link href="/es/reservar" className={botonClases({ variante: 'campana' })}>
            {copy.ctaBook}
          </Link>

          <Link href="/es" className={botonClases({ variante: 'campana-gris' })}>
            {copy.cta}
          </Link>
        </div>

        <Link
          href="/en"
          className="mt-10 inline-flex min-h-11 items-center texto-cuerpo underline underline-offset-4 transition-colors hover:text-cafe"
        >
          Looking for the English site?
        </Link>
      </main>
    </div>
  );
}
