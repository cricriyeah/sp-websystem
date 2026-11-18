import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Check, Dot, Minus, Plus, Question } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import type { ColorActividad } from '@/lib/color-actividad';
import { TarjetaEmpresa, type TextosEmpresa, type VistaEmpresa } from '@/components/tarjeta-empresa';
import { GaleriaMosaico } from '@/components/galeria-mosaico';
import type { FotoVisor } from '@/components/ui/visor-galeria';
import { TarjetaProducto, type TextosProducto, type VistaProducto } from '@/components/tarjeta-producto';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { HeroMedia } from '@/components/ui/hero-media';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';
import { Foto } from '@/components/conocenos-sede';

/** Un renglón de una lista del detalle: su título y, si lo hay, una línea que lo explica. */
export type ItemLista = { titulo: string; detalle?: string };
export type BloqueLista = { titulo: string; items: ItemLista[] };
/** Un dato de la ficha: la cifra o el lugar en grande y debajo qué es («5–6 h» · «Duración»). */
export type DatoFicha = {
  etiqueta: string;
  valor: string;
  /** Una línea chica bajo el dato («Cada quien que pesca necesita la suya»). */
  nota?: string;
  /** Un enlace bajo el dato (el mapa del punto de salida). */
  enlace?: { href: string; etiqueta: string };
};
/** Quien te lleva: la persona (o el gremio) con su retrato y dos fotos de su mar, tomados de «Conócenos» de la sede. */
export type VistaQuien = {
  nombre: string;
  /** La empresa, cuando el nombre es el de una persona. */
  empresa?: string;
  detalles: string[];
  texto?: string;
  retrato: { src: string; alt: string; posicion?: string };
  fotos: { src: string; alt: string; posicion?: string }[];
  enlace: { href: string; etiqueta: string };
};
/** Una etiqueta corta (una especie, una regla del viaje); con `href`, lleva a su guía. */
export type EtiquetaDetalle = { texto: string; href?: string };
/**
 * Un bloque propio de un servicio o paquete (`content/detalle-extra.ts`), con su forma: `dias` = una fila por día con
 * su ficha de calendario; `filas` = un dato grande con su explicación al lado; `cifras` = el recuadro arena de la ficha.
 */
export type BloqueDetalle =
  | { tipo: 'dias'; titulo: string; items: { dia: string; numero: string; titulo: string; texto: string }[] }
  | { tipo: 'filas'; titulo: string; items: { valor: string; texto: string }[]; nota?: string }
  | { tipo: 'cifras'; titulo: string; items: { valor: string; etiqueta: string }[] }
  /** Lo que se incluye o no, con el mismo signo que «Qué incluye»: palomita, guion o signo de pregunta (sin confirmar). */
  | { tipo: 'incluye'; titulo: string; items: { titulo: string; estado: 'si' | 'no' | 'pendiente'; detalle?: string }[] };
/** Un extra con su precio aparte, para leerlo como costo opcional y no como algo incluido. */
export type ExtraDetalle = { nombre: string; detalle?: string; precio: { monto: string; base?: string } };

export type VistaDetalle = {
  titulo: string;
  /** Qué es y dónde, en un renglón pequeño sobre el nombre y dentro del `h1` (como el de la sede): el nombre del
   * catálogo es corto y no dice el lugar. */
  encabezado?: string;
  /** Qué es: la descripción, en un párrafo. */
  lead: string;
  color: ColorActividad;
  /** La palabra del tipo: rotula el arranque cuando no hay foto honesta. */
  palabra: string;
  foto: { src: string; alt: string } | null;
  /** Todas sus fotos (la principal primero): con más de una, el fondo del héroe las cambia solo, como carrusel. */
  fotos: { src: string; alt: string }[];
  /** Todas las fotos del lugar, para la galería con visor; vacía = no hay galería. */
  galeria: FotoVisor[];
  /** Una línea bajo el título: quién lo opera. */
  linea: string;
  /** «Así es tu día» (servicio) o «Así es tu viaje» (paquete). */
  tituloQueEs: string;
  /** Horario, duración, cupo y punto de salida (o noches, días de mar y recogida): solo los que existen. */
  ficha: DatoFicha[];
  /** Lo que se pesca, bajo la ficha; cada especie con guía enlaza a ella. Vacía = no se pinta. */
  especies: { titulo: string; items: EtiquetaDetalle[] };
  /** Las reglas del viaje que la empresa ya confirmó («Te quedas con tu pesca»). Vacía = no se pinta. */
  reglas: { titulo: string; items: EtiquetaDetalle[] };
  /** Lo que recibe el cliente; las exclusiones del backoffice van aparte, sin palomita. */
  incluye: { titulo: string; items: ItemLista[]; noIncluye: string[] };
  extras: { titulo: string; items: ExtraDetalle[] };
  /** Listas sin lugar fijo (el «qué llevar» de la pesca cuando el catálogo no responde). */
  otros: BloqueLista[];
  /** Itinerario, temporada, qué se pesca, equipo: los bloques propios de este servicio o paquete. */
  bloques: BloqueDetalle[];
  /** Cuando una lista de «Qué incluye» no existe todavía: el enlace para preguntarlo por WhatsApp. */
  preguntaIncluye: { etiqueta: string; href: string } | null;
  compra: {
    /** `'ruta'` = el precio depende de la ruta; `null` = no hay precio que anunciar. */
    precio: { monto: string; base: string; conDesde: boolean; aprox?: string } | 'ruta' | null;
    datos: { etiqueta: string; valor: string }[];
    nota?: string;
    /** «Reserva con tranquilidad» pegado al precio: confirmación, mal clima y plazo de cambio, con su enlace. */
    condiciones: { titulo: string; renglones: string[]; enlace: { href: string; etiqueta: string } } | null;
    /** `null` = no hay a dónde reservar (el catálogo no respondió). */
    href: string | null;
    etiquetaBoton: string;
  };
  /** Va arriba, tras la ficha; sin él, las empresas van al final como antes. */
  quien: VistaQuien | null;
  empresas: VistaEmpresa[];
  tambien: { titulo: string; etiqueta: string; productos: VistaProducto[] } | null;
};

export type TextosDetalle = {
    detalle: Dictionary['sedeContenido']['detalle'];
    visor: Dictionary['sedeContenido']['galeriaVisor'];
    reservar: TextosProducto;
    carril: { anterior: string; siguiente: string };
    empresa: TextosEmpresa;
    reservarCorto: string;
    desde: string;
    tarifaRuta: string;
};

type Props = {
  vista: VistaDetalle;
  textos: TextosDetalle;
  /** Las opiniones del lugar: van tras el bloque de compra. */
  opiniones?: ReactNode;
  /** Las preguntas frecuentes: van antes de «Más para hacer», que cierra la página. */
  preguntas?: ReactNode;
};

// Clases completas para que Tailwind las vea: la franja de arriba del bloque de compra y el campo sin foto.
const FRANJA: Record<ColorActividad, string> = { mar: 'border-azul', traslado: 'border-coral', estancia: 'border-verde' };
const CAMPO: Record<ColorActividad, string> = { mar: 'bg-azul', traslado: 'bg-coral', estancia: 'bg-verde' };

/** `grande` en el bloque de compra, `heroe` sobre la foto del arranque y `chico` en la barra del teléfono. */
function Precio({ precio, textos, tamano = 'chico' }: { precio: NonNullable<VistaDetalle['compra']['precio']>; textos: Props['textos']; tamano?: 'chico' | 'heroe' | 'grande' }) {
  if (precio === 'ruta') return <span className={tamano === 'chico' ? 'font-semibold' : 'text-xl font-semibold'}>{textos.tarifaRuta}</span>;
  return (
    <>
      <strong className={cn('block tabular-nums', {
        chico: 'text-lg',
        heroe: 'texto-mono-mayus text-3xl font-bold leading-none',
        grande: 'texto-mono-mayus text-[40px] font-bold leading-none',
      }[tamano])}>
        {precio.conDesde && <span className="texto-cuerpo font-normal normal-case">{textos.desde} </span>}
        {precio.monto}
      </strong>
      <span className={cn('block', tamano === 'grande' && 'mt-3', tamano === 'heroe' && 'mt-2 texto-cuerpo')}>
        {precio.aprox && `${precio.aprox} · `}
        {precio.base}
      </span>
    </>
  );
}

/** «Reserva con tranquilidad»: confirmación, mal clima y plazo de cambio, con su enlace a la política. */
function Condiciones({ condiciones, className }: { condiciones: NonNullable<VistaDetalle['compra']['condiciones']>; className?: string }) {
  return (
    <div className={cn('flex-col gap-3 p-5', className)}>
      <p className="font-semibold">{condiciones.titulo}</p>
      <ul className="flex flex-col gap-2.5">
        {condiciones.renglones.map((renglon) => (
          <li key={renglon} className="flex items-start gap-3 texto-cuerpo">
            <Check size={18} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0" />
            {renglon}
          </li>
        ))}
      </ul>
      <Link href={condiciones.enlace.href} className="inline-flex min-h-11 items-center gap-2 self-start font-semibold underline-offset-4 hover:underline">
        {condiciones.enlace.etiqueta}
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}

/**
 * Quién te lleva, justo tras la ficha (PFD del detalle, 2026-11-17: en este nicho se compra al capitán y su panga).
 * El retrato a la izquierda; a su lado el nombre en la letra de los titulares, sus datos, una frase y el enlace a su
 * relato en la sede; debajo, dos fotos de su mar. En el teléfono, todo apilado con el retrato a lo ancho.
 */
function QuienTeLleva({ quien, titulo }: { quien: VistaQuien; titulo: string }) {
  return (
    <div>
      <h2 className="rev texto-seccion">{titulo}</h2>
      <div className="mt-8 grid gap-6 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)] sm:gap-8">
        <Foto src={quien.retrato.src} alt={quien.retrato.alt} posicion={quien.retrato.posicion} sizes="(min-width: 640px) 14rem, 100vw" className="aspect-[4/5]" />
        <div className="flex flex-col items-start gap-3 sm:pt-1">
          <p className="rev texto-mono-mayus text-2xl font-bold leading-tight text-balance sm:text-3xl">{quien.nombre}</p>
          {quien.empresa && <p className="rev texto-cuerpo font-semibold">{quien.empresa}</p>}
          {quien.detalles.length > 0 && (
            <ul className="rev flex flex-col gap-1.5">
              {quien.detalles.map((dato) => (
                <li key={dato} className="flex items-start gap-3 text-lg">
                  <Check size={20} weight="bold" aria-hidden="true" className="mt-1 shrink-0 text-cafe" />
                  {dato}
                </li>
              ))}
            </ul>
          )}
          {quien.texto && <p className="rev max-w-[48ch] text-lg leading-snug">{quien.texto}</p>}
          <Link href={quien.enlace.href} className="group/enlace inline-flex min-h-11 items-center gap-2 font-semibold text-cafe hover:text-tinta">
            {quien.enlace.etiqueta}
            <span aria-hidden="true" className="transition-transform duration-200 ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover/enlace:translate-x-1">→</span>
          </Link>
        </div>
      </div>
      {quien.fotos.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-4">
          {quien.fotos.slice(0, 2).map((foto, i) => (
            <Foto key={foto.src} src={foto.src} alt={foto.alt} posicion={foto.posicion} rapida={i === 1} sizes="(min-width: 1024px) 25vw, 50vw" className="aspect-[4/3]" />
          ))}
        </div>
      )}
    </div>
  );
}

/** La ficha de datos: el dato en la letra de los titulares sobre un campo arena y su etiqueta, chica, debajo. */
function Cifras({ items, className }: { items: { valor: string; etiqueta: string; nota?: string; enlace?: DatoFicha['enlace'] }[]; className?: string }) {
  return (
    // En el teléfono cada dato es un renglón (la etiqueta a la izquierda, el dato a la derecha): en dos columnas de
    // 140 px los datos largos se partían en tres líneas y la etiqueta quedaba lejos de su dato (dueño, 2026-11-17).
    // Desde `sm`, las casillas: el dato grande y su etiqueta, chica, debajo; la nota y el enlace al final.
    <dl className={cn('rev grid grid-cols-1 gap-y-5 bg-cafe-bruma p-6 sm:grid-cols-2 sm:gap-x-6 sm:gap-y-7 sm:p-8', className)}>
      {items.map((dato) => (
        <div key={`${dato.valor}-${dato.etiqueta}`} className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-baseline gap-x-4 gap-y-1 sm:flex sm:flex-col sm:items-start sm:gap-1.5">
          <dt className="texto-pequeno sm:order-2">{dato.etiqueta}</dt>
          <dd className="texto-mono-mayus text-lg font-bold leading-tight text-balance sm:order-1 sm:text-xl">{dato.valor}</dd>
          {(dato.nota || dato.enlace) && (
          <dd className="col-start-2 flex flex-col items-start gap-1 sm:order-3">
            {dato.nota && <span className="texto-pequeno text-foreground">{dato.nota}</span>}
            {dato.enlace && (
              <a href={dato.enlace.href} target="_blank" rel="noopener noreferrer" className="-my-2 inline-flex min-h-11 items-center gap-1 texto-pequeno font-semibold text-cafe hover:text-tinta">
                {dato.enlace.etiqueta}
                <ArrowUpRight size={14} weight="bold" aria-hidden="true" />
              </a>
            )}
          </dd>
          )}
        </div>
      ))}
    </dl>
  );
}

/**
 * Etiquetas cortas en fila (especies, reglas): rectángulos arena con la palabra; la que tiene guía es un enlace que
 * se entinta al pasar. Con `marca`, cada una lleva la palomita de «Qué incluye» (son reglas, no temas).
 */
function Etiquetas({ titulo, items, marca }: { titulo: string; items: EtiquetaDetalle[]; marca?: boolean }) {
  if (items.length === 0) return null;
  return (
    <div className="rev mt-6 flex flex-col gap-3">
      <p className="texto-pequeno">{titulo}</p>
      <ul className="flex flex-wrap gap-2">
        {items.map((item) => {
          const contenido = (
            <>
              {marca && <Check size={16} weight="bold" aria-hidden="true" className="shrink-0 text-cafe" />}
              {item.texto}
              {item.href && <ArrowUpRight size={14} weight="bold" aria-hidden="true" className="shrink-0" />}
            </>
          );
          const forma = 'inline-flex min-h-11 items-center gap-2 bg-cafe-bruma px-4 text-base font-semibold';
          return (
            <li key={item.texto}>
              {item.href ? (
                <Link href={item.href} className={cn(forma, 'transition-colors hover:bg-tinta hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring')}>
                  {contenido}
                </Link>
              ) : (
                <span className={forma}>{contenido}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Los bloques propios. El itinerario es un `<ol>`: cada día lleva su ficha de calendario en el color del producto
 * («Días» chico arriba, «2–5» grande), y a su lado qué pasa ese día. «Qué se pesca» pone el dato grande a la
 * izquierda y la explicación a la derecha; sin líneas: los renglones se separan con espacio.
 */
function Bloque({ bloque, color }: { bloque: BloqueDetalle; color: ColorActividad }) {
  return (
    <div>
      <h2 className="rev texto-seccion">{bloque.titulo}</h2>
      {bloque.tipo === 'dias' && (
        <ol className="mt-8 flex flex-col gap-8">
          {bloque.items.map((dia) => (
            <li key={dia.numero} className="rev grid grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-5 sm:grid-cols-[6.5rem_minmax(0,1fr)] sm:gap-8">
              <span className={cn('flex aspect-square flex-col items-center justify-center text-white', CAMPO[color])}>
                <span className="texto-pequeno">{dia.dia}</span>
                <span className="texto-mono-mayus text-3xl font-bold leading-none sm:text-4xl">{dia.numero}</span>
              </span>
              <span className="pt-1">
                <span className="block texto-mono-mayus text-xl font-bold leading-tight">{dia.titulo}</span>
                <span className="mt-2 block max-w-[52ch] text-lg leading-snug">{dia.texto}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
      {bloque.tipo === 'filas' && (
        <>
          <dl className="mt-8 flex flex-col gap-6">
            {bloque.items.map((fila) => (
              <div key={fila.valor} className="rev grid gap-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-baseline sm:gap-8">
                <dt className="texto-mono-mayus text-2xl font-bold leading-tight sm:text-3xl">{fila.valor}</dt>
                <dd className="text-lg leading-snug">{fila.texto}</dd>
              </div>
            ))}
          </dl>
          {bloque.nota && <p className="rev mt-6 texto-cuerpo">{bloque.nota}</p>}
        </>
      )}
      {bloque.tipo === 'cifras' && <Cifras items={bloque.items} className="mt-8" />}
      {bloque.tipo === 'incluye' && (
        <ul className="mt-6 grid gap-x-10 gap-y-4 sm:grid-cols-2">
          {bloque.items.map((item) => {
            const Signo = item.estado === 'si' ? Check : item.estado === 'no' ? Minus : Question;
            return (
              <li key={item.titulo} className="rev flex items-start gap-3">
                <Signo size={22} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" />
                <span>
                  <span className="block text-lg font-semibold leading-snug">{item.titulo}</span>
                  {item.detalle && <span className="mt-1 block texto-cuerpo">{item.detalle}</span>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/**
 * El detalle de un servicio o de un paquete, el mismo diseño para los dos. Orden derivado con perception-first-design
 * (2026-11-17), el de las preguntas de quien compara antes de pagar: el arranque con precio y botón; la ficha con todo
 * lo que decide (horario, duración, cupo, equipo, licencia, salida); quién te lleva con sus fotos; lo que incluye y lo
 * que no; el bloque de compra fijo al lado (en el teléfono, una barra fija abajo y las condiciones tras «Quién te
 * lleva»); las opiniones; las preguntas, y al final lo demás de la sede. Lo que no tiene contenido real no se pinta.
 *
 * Server Component.
 */
export function DetalleProducto({ vista, textos, opiniones, preguntas }: Props) {
  const { compra } = vista;
  const arranque = (
    <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col justify-end gap-6 px-pagina pb-10 pt-[calc(var(--nav-alto)+0.5rem)] text-hero-ink sm:pb-14">
      <div className="mb-auto flex flex-col items-start gap-6">
        {!vista.foto && <span aria-hidden="true" className="texto-gigante">{vista.palabra}</span>}
      </div>
      <h1 className="texto-grande">
        {vista.encabezado && <span className="mb-2 block texto-etiqueta">{vista.encabezado}</span>}
        {vista.titulo}
      </h1>
      <p className="max-w-[52ch] text-xl leading-snug">{vista.linea}</p>
      {/* El precio y el botón en el arranque: la señal principal se ve antes de bajar. Volver a la sede es
          «‹ La Paz» en la esquina del logo (`EsquinaBarra`), la misma en todo el sitio: aquí nada compite con reservar. */}
      {compra.href && (
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          {compra.precio && <p><Precio precio={compra.precio} textos={textos} tamano="heroe" /></p>}
          <Link href={compra.href} className={botonClases({ variante: 'campana-claro' })}>{textos.detalle.reservarFecha}</Link>
        </div>
      )}
    </div>
  );

  return (
    <div className="pb-[calc(4.75rem+var(--aviso-alto,0px))] md:pb-0">
      <section>
        {vista.foto ? (
          <HeroMedia imagen={vista.foto.src} imagenes={vista.fotos} video={null} alt={vista.foto.alt} preload alto="media">{arranque}</HeroMedia>
        ) : (
          <div className={cn('flex min-h-[max(28.75rem,min(70svh,45rem))] flex-col', CAMPO[vista.color])}>{arranque}</div>
        )}
      </section>

      <section className="bg-superficie py-16 sm:py-20 lg:py-28">
        <div className="mx-auto grid max-w-[1440px] items-start gap-12 px-pagina lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,1fr)] lg:gap-24">
          <div className="flex flex-col gap-12 lg:gap-16">
            {(vista.lead || vista.ficha.length > 0) && (
              <div>
                <h2 className="rev texto-seccion">{vista.tituloQueEs}</h2>
                {vista.lead && <p className="mt-5 max-w-[52ch] whitespace-pre-line text-xl leading-snug">{vista.lead}</p>}
                {/* La ficha: todo lo que decide la compra en un solo campo arena (a qué hora, cuánto dura, cuántos caben,
                    qué equipo llevas, la licencia y de dónde sale); la etiqueta, chica, debajo de cada dato. */}
                {vista.ficha.length > 0 && <Cifras items={vista.ficha} className={cn('mt-8', vista.ficha.length > 4 && 'sm:grid-cols-3')} />}
                {/* Lo que se pesca y las reglas del viaje: el mismo «cómo es tu día», en palabras sueltas. */}
                <Etiquetas titulo={vista.especies.titulo} items={vista.especies.items} />
                <Etiquetas titulo={vista.reglas.titulo} items={vista.reglas.items} marca />
              </div>
            )}
            {/* Itinerario, temporada, qué se pesca: el resto de «cómo es», pegado a la ficha. */}
            {vista.bloques.map((bloque) => (
              <Bloque key={bloque.titulo} bloque={bloque} color={vista.color} />
            ))}
            {vista.quien && <QuienTeLleva quien={vista.quien} titulo={textos.detalle.quienOpera} />}
            {/* En el teléfono el bloque de compra va hasta abajo: las condiciones se adelantan aquí. */}
            {compra.condiciones && <Condiciones condiciones={compra.condiciones} className="rev flex bg-cafe-bruma lg:hidden" />}
            {vista.galeria.length > 0 && (
              <div>
                <h2 className="rev texto-seccion">{textos.detalle.galeria}</h2>
                <GaleriaMosaico fotos={vista.galeria} textosVisor={textos.visor} />
              </div>
            )}
            {vista.incluye.items.length > 0 && (
              <div>
                <h2 className="rev texto-seccion">{vista.incluye.titulo}</h2>
                <ul className="mt-6 grid gap-x-10 gap-y-4 sm:grid-cols-2">
                  {vista.incluye.items.map((item) => (
                    <li key={item.titulo} className="rev flex items-start gap-3">
                      <Check size={22} weight="bold" aria-hidden="true" className="mt-0.5 shrink-0 text-cafe" />
                      <span>
                        <span className="block text-lg font-semibold leading-snug">{item.titulo}</span>
                        {item.detalle && <span className="mt-1 block texto-cuerpo">{item.detalle}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
                {vista.incluye.noIncluye.length > 0 && (
                  <ul className="mt-6 flex flex-col gap-2 texto-cuerpo">
                    {vista.incluye.noIncluye.map((renglon) => (
                      <li key={renglon} className="flex items-start gap-3">
                        <Minus size={22} weight="bold" aria-hidden="true" className="mt-px shrink-0" />
                        {renglon}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {vista.extras.items.length > 0 && (
              <div>
                <h2 className="rev texto-seccion">{vista.extras.titulo}</h2>
                {/* Cada extra como una fila de precio: el «+» y el monto a la derecha dicen que cuesta aparte. */}
                <ul className="mt-6 flex flex-col gap-2">
                  {vista.extras.items.map((extra) => (
                    <li key={extra.nombre} className="rev flex items-center justify-between gap-6 bg-cafe-bruma px-5 py-4">
                      <span className="flex items-start gap-3">
                        <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-full bg-tinta text-white">
                          <Plus size={16} weight="bold" />
                        </span>
                        <span>
                          <span className="block text-lg font-semibold leading-snug">{extra.nombre}</span>
                          {extra.detalle && <span className="mt-1 block texto-cuerpo">{extra.detalle}</span>}
                        </span>
                      </span>
                      <span className="shrink-0 text-right tabular-nums">
                        <span className="block text-lg font-semibold">{extra.precio.monto}</span>
                        {extra.precio.base && <span className="block texto-pequeno">{extra.precio.base}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {vista.otros.map((bloque) => (
              <div key={bloque.titulo}>
                <h2 className="rev texto-seccion">{bloque.titulo}</h2>
                <ul className="mt-6 grid gap-x-10 gap-y-3 sm:grid-cols-2">
                  {bloque.items.map((item) => (
                    <li key={item.titulo} className="rev flex items-start gap-2 text-lg">
                      <Dot size={28} weight="bold" aria-hidden="true" className="-mt-0.5 shrink-0 text-cafe" />
                      {item.titulo}
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
                <Precio precio={compra.precio} textos={textos} tamano="grande" />
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
            {/* Lo que se pregunta antes de pagar, donde se paga. En el teléfono ya salió tras «Quién te lleva». */}
            {compra.condiciones && <Condiciones condiciones={compra.condiciones} className="hidden bg-hero-ink/10 lg:flex" />}
          </aside>
        </div>
      </section>

      {opiniones}

      {/* Sin «Quién te lleva» arriba (o con varias empresas), las empresas van aquí. */}
      {vista.empresas.length > 0 && (!vista.quien || vista.empresas.length > 1) && (
        <section aria-labelledby="detalle-opera" className="bg-superficie py-16 sm:py-20 lg:py-28">
          <div className="mx-auto max-w-[1440px] px-pagina">
            <h2 id="detalle-opera" className="rev texto-seccion">{textos.detalle.quienOpera}</h2>
            <ul className="mt-10 flex flex-col gap-12">
              {vista.empresas.map((empresa) => (
                <TarjetaEmpresa key={empresa.slug} empresa={empresa} textos={textos.empresa} horizontal />
              ))}
            </ul>
          </div>
        </section>
      )}

      {preguntas}

      {vista.tambien && vista.tambien.productos.length > 0 && (
        // Arena: cierra la página tras las preguntas, que van en blanco.
        <section aria-labelledby="detalle-tambien" className="bg-cafe-bruma py-16 sm:py-20 lg:py-28">
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
        <div className="fixed inset-x-0 bottom-[var(--aviso-alto,0px)] z-[var(--z-barra)] flex items-center justify-between gap-4 bg-tinta px-pagina pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 text-hero-ink transition-[bottom] duration-200 md:hidden">
          <p className="font-semibold tabular-nums">{compra.precio && <Precio precio={compra.precio} textos={textos} />}</p>
          <Link href={compra.href} className={botonClases({ variante: 'campana-claro' })}>{textos.reservarCorto}</Link>
        </div>
      )}
    </div>
  );
}
