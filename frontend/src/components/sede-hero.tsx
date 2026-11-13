import Link from 'next/link';
import Image from 'next/image';
import type { SedeHeroContenido } from '@/content/sedes-tipos';
import type { LogoLargo } from '@/content/empresas-marca';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { PalabraRota } from '@/components/palabra-rota';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';

type SedeHeroProps = {
  nombre: string;
  contenido: SedeHeroContenido;
  /** Lo que vende la sede, sacado de su catálogo (`palabrasDeSede`); vacío si el catálogo no respondió. */
  palabras: string[];
  /** La empresa local que opera la sede; sin ella no hay sello. */
  empresa?: { nombre: string; logo?: string; simbolo?: string; simboloBarra?: string; logoLargo?: LogoLargo };
  /** El logo de la empresa suelto, sin el círculo del sello (cuando el logo ya trae su disco). */
  empresaSinCirculo?: boolean;
  textos: { cta: string };
};

/**
 * Arranque de campaña de una sede (F10): el video del mar a pantalla completa, desde el borde de
 * arriba (la barra flota encima), una palabra gigante que cambia con lo que se reserva ahí, el nombre
 * de la sede como `h1`, una frase y un solo botón que baja a lo que se puede reservar. Lo comparten las
 * tres sedes.
 *
 * Acomodo por PFD (dueño, 2026-11-13: «se ve demasiado cluttered»). La palabra que rota es lo único gigante;
 * abajo van dos grupos separados por un espacio mayor que el de adentro: a la izquierda quién y dónde (renglón,
 * nombre y una frase corta) y a la derecha la acción (la empresa con la que sales, encima del botón). El logo
 * nunca pesa más que el nombre. En el teléfono la empresa y el botón comparten la última fila. Todo cabe en una
 * pantalla; el resto de la presentación va bajo «Elige tu salida» (`hero.presentacion`).
 *
 * Server Component (la palabra que rota es una isla cliente).
 */
export function SedeHero({ nombre, contenido, palabras, empresa, empresaSinCirculo = false, textos }: SedeHeroProps) {
  return (
    <section>
      <HeroMedia imagen={contenido.imagen} video={contenido.video} alt={contenido.alt ?? ""} preload alto="completo" objectPosition={contenido.posicionImagen} objectPositionMovil={contenido.posicionImagenMovil} objectPositionVideoMovil={contenido.posicionVideoMovil}>
        <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-between gap-8 px-pagina pb-8 pt-[calc(var(--nav-alto)+1.5rem)] text-hero-ink sm:pb-14">
          {palabras.length > 0 ? <PalabraRota palabras={palabras} className="texto-gigante" /> : <span />}
          <div className="grid gap-y-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end lg:gap-x-16">
            <div>
              <h1 className="texto-grande">
                {contenido.encabezado && <span className="mb-2 block texto-etiqueta">{contenido.encabezado}</span>}
                {nombre}
              </h1>
              <p className="mt-4 max-w-[46ch] text-lg leading-snug sm:text-xl">{contenido.subtitulo}</p>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 lg:flex-col lg:items-end lg:justify-end lg:gap-y-5">
              {empresa?.logoLargo ? (
                // El logo largo ya dice el nombre de la empresa: va solo, sin el sello ni el «Con …», y en blanco como el texto
                // del héroe (a color no se lee sobre el video; el dueño eligió el blanco, 2026-10-30). Del alto de sello de la
                // marca (Piratas, de puras letras, más bajo); por defecto el de Sal y Sol.
                <Image
                  src={empresa.logoLargo.blanco ?? empresa.logoLargo.src}
                  alt={empresa.nombre}
                  width={empresa.logoLargo.ancho}
                  height={empresa.logoLargo.alto}
                  className={`block w-auto ${empresa.logoLargo.sello ?? 'h-12 sm:h-14 lg:h-16'}`}
                />
              ) : empresa && (
                // Sin logo largo, solo el sello, sin el «Con …» al lado: como las demás sedes, un logo junto al botón
                // (dueño, 2026-11-13). El nombre va en el `alt` del sello.
                <EmpresaSello nombre={empresa.nombre} logo={empresa.simbolo ?? empresa.logo} tamano={64} sinCirculo={empresaSinCirculo} />
              )}
              <Link href={`#${ANCLA_DE.reservar}`} className={botonClases({ variante: 'campana-claro' })}>
                {textos.cta}
              </Link>
            </div>
          </div>
        </div>
      </HeroMedia>
    </section>
  );
}
