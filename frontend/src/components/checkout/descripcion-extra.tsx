import type { Locale } from '@/app/[lang]/dictionaries';
import { textoLocalizado, type TextoLocalizado } from '@/lib/texto-localizado';

/** El texto de un extra en el idioma de la página; '' si no tiene (entonces no se pinta nada, ni hueco). */
export function textoDeExtra(descripcion: TextoLocalizado | undefined, lang: Locale): string {
  return textoLocalizado(descripcion, lang);
}

/** Descripción corta bajo el nombre de un extra. El control la referencia con `aria-describedby={id}`. */
export function DescripcionExtra({ id, texto }: { id: string; texto: string }) {
  if (!texto) return null;
  return (
    <span id={id} className="mt-0.5 block texto-pequeno text-muted">
      {texto}
    </span>
  );
}
