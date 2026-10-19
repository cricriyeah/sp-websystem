import { EmpresaSello } from '@/components/ui/empresa-sello';

type BandaColaboracionProps = {
  /** La empresa protagonista de la sede. Sin ella no hay banda. */
  empresa: { nombre: string; logo?: string };
  /** `dict.sedeContenido.colaboracion`, con `{empresa}` por reemplazar. */
  frase: string;
};

/**
 * La frase que dice de quién es la sede: Sun Baja Experience con la empresa local. Franja
 * delgada bajo el héroe, sin `h2` y fuera del menú: no es una sección, es el pie del héroe.
 * El sello va oculto a lectores porque el nombre ya está en la frase.
 *
 * Server Component.
 */
export function BandaColaboracion({ empresa, frase }: BandaColaboracionProps) {
  return (
    <div className="bg-background">
      <p className="mx-auto flex max-w-[1120px] items-center gap-3 px-4 py-4 texto-pequeno text-tinta-suave sm:px-6 lg:px-8">
        <span aria-hidden="true" className="inline-flex">
          <EmpresaSello nombre={empresa.nombre} logo={empresa.logo} tamano={24} />
        </span>
        <span>{frase.replace('{empresa}', empresa.nombre)}</span>
      </p>
    </div>
  );
}
