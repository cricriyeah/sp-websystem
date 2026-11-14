import Link from 'next/link';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Guia } from '@/content/guias';
import { hrefGuias } from '@/lib/routes';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import { ListaGuias } from '@/components/lista-guias';

type Props = {
  id: string;
  lang: Locale;
  guias: readonly Guia[];
  fondo: Fondo;
  textos: { titulo: string; verTodas: string };
};

/**
 * «Antes de venir»: las guías de la sede (cuándo ir, qué se ve, cómo llegar), justo antes de las preguntas
 * frecuentes. Dos por renglón en escritorio, para que no quede un renglón de orilla a orilla con una frase corta.
 * «Ver todas» lleva al índice, que es del hub: en modo «solo sede» se esconde.
 *
 * Server Component.
 */
export function GuiasSede({ id, lang, guias, fondo, textos }: Props) {
  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
      <ListaGuias lang={lang} guias={guias} bloque={fondo === 'blanco' ? 'bg-cafe-bruma' : 'bg-superficie'} columnas className="mt-10" />
      <Link href={hrefGuias(lang)} className="sale-al-hub mt-8 inline-flex min-h-11 items-center texto-cuerpo font-semibold underline underline-offset-4">
        {textos.verTodas}
      </Link>
    </SectionShell>
  );
}
