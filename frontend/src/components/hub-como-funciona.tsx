import type { ComponentType } from 'react';
import type { IconProps } from '@phosphor-icons/react';
import { CreditCard, MapPinLine, UsersThree } from '@phosphor-icons/react/ssr';

type Props = {
  id: string;
  titulo: string;
  texto: string;
  pasos: { titulo: string; texto: string }[];
};

const ICONOS: ComponentType<IconProps>[] = [MapPinLine, CreditCard, UsersThree];

/**
 * Cómo funciona el sitio: un lugar que reúne a las empresas locales, cada una opera y cobra
 * directo. Tres filas sin numerales ni conectores (el orden lo da el DOM), en una banda
 * café bruma; desde 1024 px, título a la izquierda (5/12) y filas a la derecha (7/12).
 *
 * Server Component.
 */
export function HubComoFunciona({ id, titulo, texto, pasos }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-[calc(var(--nav-alto)+16px)] border-t border-borde bg-cafe-bruma py-12 sm:py-16 lg:py-24">
      <div className="mx-auto grid max-w-[1120px] gap-10 px-4 sm:px-6 lg:grid-cols-12 lg:gap-12 lg:px-8">
        <div className="lg:col-span-5">
          <h2 id={`${id}-titulo`} className="max-w-[16ch] texto-seccion text-foreground">{titulo}</h2>
          <p className="mt-4 max-w-[46ch] texto-cuerpo text-tinta-suave">{texto}</p>
        </div>
        <ol className="flex flex-col gap-8 lg:col-span-7">
          {pasos.map((paso, i) => {
            const Icono = ICONOS[i] ?? MapPinLine;
            return (
              <li key={paso.titulo} className="flex items-start gap-4">
                <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-full border border-borde bg-blanco">
                  <Icono size={24} aria-hidden="true" className="text-cafe" />
                </span>
                <div>
                  <h3 className="texto-subtitulo text-foreground">{paso.titulo}</h3>
                  <p className="mt-1 max-w-[60ch] texto-cuerpo text-tinta-suave">{paso.texto}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
