import Link from 'next/link';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { ColorActividad } from '@/lib/color-actividad';
import { TarjetaEmpresa, type TextosEmpresa, type VistaEmpresa } from '@/components/tarjeta-empresa';
import { TarjetaProducto, type TextosProducto, type VistaProducto } from '@/components/tarjeta-producto';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

/** Un renglón de una lista del detalle: su título y, si lo hay, una línea que lo explica. */
export type ItemLista = { titulo: string; detalle?: string };
export type BloqueLista = { titulo: string; items: ItemLista[] };

export type VistaDetalle = {
  titulo: string;
  /** Qué es: la descripción, en un párrafo. */
  lead: string;
  color: ColorActividad;
  /** La palabra del tipo: rotula el arranque cuando no hay foto honesta. */
  palabra: string;
  foto: { src: string; alt: string } | null;
  /** Una línea bajo el título: quién lo opera. */
  linea: string;
  volver: { href: string; etiqueta: string };
  bloques: BloqueLista[];
  /** Cuando una lista de «Qué incluye» no existe todavía: el enlace para preguntarlo por WhatsApp. */
  preguntaIncluye: { etiqueta: string; href: string } | null;
  compra: {
    /** `'ruta'` = el precio depende de la ruta; `null` = no hay precio que anunciar. */
    precio: { monto: string; base: string; conDesde: boolean; aprox?: string } | 'ruta' | null;
    datos: { etiqueta: string; valor: string }[];
    nota?: string;
    /** `null` = no hay a dónde reservar (el catálogo no respondió). */
    href: string | null;
    etiquetaBoton: string;
  };
  empresas: VistaEmpresa[];
  tambien: { titulo: string; etiqueta: string; productos: VistaProducto[] } | null;
};

export type TextosDetalle = {
    detalle: Dictionary['sedeContenido']['detalle'];
    reservar: TextosProducto;
    carril: { anterior: string; siguiente: string };
    empresa: TextosEmpresa;
    reservarCorto: string;
    desde: string;
    tarifaRuta: string;
};

type Props = { vista: VistaDetalle; textos: TextosDetalle };

// Clases completas para que Tailwind las vea: la franja de arriba del bloque de compra y el campo sin foto.
const FRANJA: Record<ColorActividad, string> = { mar: 'border-azul', traslado: 'border-coral', estancia: 'border-verde' };
const CAMPO: Record<ColorActividad, string> = { mar: 'bg-azul', traslado: 'bg-coral', estancia: 'bg-verde' };

function Precio({ precio, textos, grande }: { precio: NonNullable<VistaDetalle['compra']['precio']>; textos: Props['textos']; grande?: boolean }) {
  if (precio === 'ruta') return <span className={grande ? 'text-xl font-semibold' : 'font-semibold'}>{textos.tarifaRuta}</span>;
  return (
    <>
      <strong className={cn('block tabular-nums', grande ? 'texto-mono-mayus text-[40px] font-bold leading-none' : 'text-lg')}>
        {precio.conDesde && <span className="texto-cuerpo font-normal normal-case">{textos.desde} </span>}
        {precio.monto}
      </strong>
      <span className={cn('block', grande && 'mt-3')}>
        {precio.aprox && `${precio.aprox} · `}
        {precio.base}
      </span>
    </>
  );
}

/**
 * El detalle de un servicio o de un paquete (F10), el mismo diseño para los dos: arranque con foto (o con un
 * campo del color de su tipo y su palabra), ficha en dos columnas con lo que es, lo que incluye y lo que se puede
 * agregar, el bloque de compra que se queda fijo al lado (en el teléfono, una barra fija abajo), quién lo opera
 * y los demás servicios de la sede. Lo que no tiene contenido real no se pinta.
 *
 * Server Component.
 */
export function DetalleProducto({ vista, textos }: Props) {
  const { compra } = vista;
  const arranque = (
    <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-end gap-6 px-4 pb-10 pt-[calc(var(--nav-alto)+1.5rem)] text-hero-ink sm:px-6 sm:pb-14 lg:px-12">
      {!vista.foto && <span aria-hidden="true" className="texto-gigante mb-auto">{vista.palabra}</span>}
      <h1 className="texto-grande">{vista.titulo}</h1>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
        <p className="max-w-[52ch] text-xl leading-snug">{vista.linea}</p>
        <Link href={vista.volver.href} className={botonClases({ variante: 'campana-claro' })}>{vista.volver.etiqueta}</Link>
      </div>
    </div>
  );

  return (
    <div className="pb-[calc(4.75rem+var(--aviso-alto,0px))] md:pb-0">
      <section>
        {vista.foto ? (
          <HeroMedia imagen={vista.foto.src} video={null} alt={vista.foto.alt} preload alto="media">{arranque}</HeroMedia>
        ) : (
          <div className={cn('flex min-h-[max(28.75rem,min(70svh,45rem))] flex-col', CAMPO[vista.color])}>{arranque}</div>
        )}
      </section>

      <section className="bg-superficie py-16 sm:py-20 lg:py-28">
        <div className="mx-auto grid max-w-[1440px] items-start gap-12 px-4 sm:px-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,1fr)] lg:gap-24 lg:px-12">
          <div className="flex flex-col gap-12 lg:gap-16">
            {vista.lead && (
              <div>
                <h2 className="rev texto-seccion">{textos.detalle.queEs}</h2>
                <p className="mt-5 max-w-[52ch] whitespace-pre-line text-xl leading-snug">{vista.lead}</p>
              </div>
            )}
            {vista.bloques.map((bloque) => (
              <div key={bloque.titulo}>
                <h2 className="rev texto-seccion">{bloque.titulo}</h2>
                <ul className="mt-5 flex flex-col gap-2">
                  {bloque.items.map((item) => (
                    <li key={item.titulo} className="rev bg-cafe-bruma px-5 py-4 font-semibold">
                      {item.titulo}
                      {item.detalle && <span className="mt-1 block font-normal texto-cuerpo">{item.detalle}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {vista.preguntaIncluye && (
              <a href={vista.preguntaIncluye.href} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center self-start font-semibold text-cafe">
                {vista.preguntaIncluye.etiqueta}
              </a>
            )}
          </div>

          <aside
            id="comprar"
            aria-label={compra.etiquetaBoton}
            className={cn('flex flex-col gap-6 border-t-[10px] bg-tinta p-6 text-hero-ink sm:p-9 lg:sticky lg:top-[calc(var(--nav-alto)+1.5rem)]', FRANJA[vista.color])}
          >
            {compra.precio && (
              <p>
                <Precio precio={compra.precio} textos={textos} grande />
              </p>
            )}
            {compra.datos.length > 0 && (
              <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-2.5">
                {compra.datos.map((dato) => (
                  <div key={dato.etiqueta} className="contents">
                    <dt>{dato.etiqueta}</dt>
                    <dd className="font-semibold">{dato.valor}</dd>
                  </div>
                ))}
              </dl>
            )}
            {compra.href && (
              <Link href={compra.href} className={cn(botonClases({ variante: 'campana-claro', bloque: true }))}>{compra.etiquetaBoton}</Link>
            )}
            {compra.nota && <p className="texto-cuerpo">{compra.nota}</p>}
          </aside>
        </div>
      </section>

      {vista.empresas.length > 0 && (
        <section aria-labelledby="detalle-opera" className="bg-superficie py-16 sm:py-20 lg:py-28">
          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-12">
            <h2 id="detalle-opera" className="rev texto-seccion">{textos.detalle.quienOpera}</h2>
            <ul className="mt-10 flex flex-col gap-12">
              {vista.empresas.map((empresa) => (
                <TarjetaEmpresa key={empresa.slug} empresa={empresa} textos={textos.empresa} horizontal />
              ))}
            </ul>
          </div>
        </section>
      )}

      {vista.tambien && vista.tambien.productos.length > 0 && (
        <section aria-labelledby="detalle-tambien" className="bg-superficie py-16 sm:py-20 lg:py-28">
          <FilaArrastrable
            cabeza={<h2 id="detalle-tambien" className="rev texto-seccion">{vista.tambien.titulo}</h2>}
            etiqueta={vista.tambien.etiqueta}
            textos={textos.carril}
          >
            {vista.tambien.productos.map((producto) => (
              <TarjetaProducto key={producto.clave} vista={producto} textos={textos.reservar} />
            ))}
          </FilaArrastrable>
        </section>
      )}

      {compra.href && (
        <div className="fixed inset-x-0 bottom-[var(--aviso-alto,0px)] z-[var(--z-barra)] flex items-center justify-between gap-4 bg-tinta px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 text-hero-ink transition-[bottom] duration-200 sm:px-6 md:hidden">
          <p className="font-semibold tabular-nums">{compra.precio && <Precio precio={compra.precio} textos={textos} />}</p>
          <Link href={compra.href} className={botonClases({ variante: 'campana-claro' })}>{textos.reservarCorto}</Link>
        </div>
      )}
    </div>
  );
}
