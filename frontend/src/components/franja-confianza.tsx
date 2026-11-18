import Link from 'next/link';
import { ArrowRight, ChatCircleText, CloudRain, CreditCard } from '@phosphor-icons/react/ssr';
import type { Icon } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type Props = {
  textos: Dictionary['sedeContenido']['franja'];
  /** El ancla de las opiniones si la sede las pinta; sin ellas no hay tercer bloque (nunca un enlace a nada). */
  opiniones: string | null;
};

/**
 * Un bloque de la banda: el ícono en un círculo `cafe-claro` (el acento de la banda tinta, como las cifras de «Reserva
 * con tranquilidad»; círculo, nunca radio intermedio) y a su lado el rótulo en la letra de los titulares. En el teléfono
 * el rótulo va SIEMPRE en dos renglones (`\n` en el diccionario): en uno no caben a 390 px y, con uno de dos y otros de
 * uno, la banda quedaba dispareja. Desde 640 px cabe en uno y lleva debajo la frase que lo cumple.
 */
function Bloque({ icono: Icono, rotulo, frase, flecha = false }: { icono: Icon; rotulo: string; frase: string; flecha?: boolean }) {
  return (
    <span className="flex items-center gap-2 sm:items-start sm:gap-4">
      <span aria-hidden="true" className="flex size-7 shrink-0 items-center justify-center rounded-full bg-cafe-claro text-tinta sm:size-10">
        <Icono weight="bold" className="size-4 sm:size-5" />
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-2 whitespace-pre-line texto-mono-mayus text-[0.75rem] font-bold leading-[1.15] sm:whitespace-normal sm:text-base sm:leading-tight lg:text-lg">
          {rotulo}
          {flecha && (
            <ArrowRight
              weight="bold"
              aria-hidden="true"
              className="hidden size-4 shrink-0 transition-transform duration-300 ease-[var(--curva-estandar)] group-hover:translate-x-1 motion-reduce:transition-none sm:block"
            />
          )}
        </span>
        <span className="mt-1.5 hidden max-w-[34ch] texto-pequeno sm:block">{frase}</span>
      </span>
    </span>
  );
}

/**
 * La franja bajo el héroe de la sede (PFD, 2026-11-17): las razones para confiar antes de pedir la decisión.
 *
 * - Pago en línea con tarjeta: la ventaja que la competencia no tiene (aparta por WhatsApp).
 * - Mal clima: la regla de «Reserva con tranquilidad», cierta en las cuatro empresas.
 * - Opiniones: baja a la sección; sin opiniones confirmadas no hay bloque.
 *
 * La misma banda en teléfono y computadora (dueño, 2026-11-17): negra, pegada al héroe, tres columnas iguales, en la voz
 * del sitio (docs/design). En el teléfono es baja (ícono y rótulo de dos renglones); en computadora el mismo bloque con
 * más aire y la frase debajo del rótulo. Sin velo sobre el héroe: ensuciaba el pie de la foto. Monta un píxel sobre el
 * héroe para que no quede una raya entre los dos.
 *
 * Sin promedio ni estrellas (decisión del dueño, 2026-11-11). Sin plazo de cambio: depende de lo que se compre (48 h,
 * 30 días, 24 h) y una sede vende varias cosas; el plazo exacto está en el detalle y en «Reserva con tranquilidad».
 *
 * Server Component.
 */
export function FranjaConfianza({ textos, opiniones }: Props) {
  return (
    <section aria-label={textos.etiqueta} className="relative -mt-px bg-tinta text-hero-ink">
      <ul className="mx-auto grid max-w-[1440px] grid-cols-3 gap-x-3 px-pagina py-4 sm:gap-x-8 sm:py-7 lg:py-9">
        <li>
          <Bloque icono={CreditCard} rotulo={textos.pagoCorto} frase={textos.pago} />
        </li>
        <li>
          <Bloque icono={CloudRain} rotulo={textos.climaCorto} frase={textos.clima} />
        </li>
        {opiniones && (
          <li>
            <Link
              href={opiniones}
              className="group block transition-opacity active:opacity-70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <Bloque icono={ChatCircleText} rotulo={textos.opinionesCorto} frase={textos.opiniones} flecha />
            </Link>
          </li>
        )}
      </ul>
    </section>
  );
}
