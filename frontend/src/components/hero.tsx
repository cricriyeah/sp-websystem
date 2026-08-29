import { BookingBar } from '@/components/booking-bar';
import { ID_BARRA_PORTADA } from '@/components/sticky-booking-bar';
import type { Locale, Dictionary } from '@/app/[lang]/dictionaries';

type HeroProps = {
  lang: Locale;
  dict: Dictionary;
  minDate: string;
};

/**
 * Portada: foto a sangre, barra de reserva montada sobre ella y la fila de
 * datos del viaje.
 *
 * **La barra de reserva encima de la foto es la pieza que define el sitio.** Es
 * lo que separa una pagina de reservas de un folleto: la conversion vive arriba,
 * no al final. La fila de datos que va debajo estaba antes dentro de "Nosotros",
 * donde llegaba demasiado tarde para ayudar a decidir.
 *
 * **La entrada del titular no retrasa nada.** Titular y subtitulo entran con
 * `.titulo-entra` (globals.css): sube y aparece, empieza en el primer cuadro y
 * termina en medio segundo. No se usan las clases `.rev` de las secciones de
 * abajo, que esperan a que el bloque entre en pantalla — aqui ya estamos en
 * pantalla, y un titular que tarda en existir es el peor primer segundo posible.
 * La barra de reserva **no** se anima: es la accion, y tiene que poder tocarse
 * desde el primer cuadro.
 *
 * La barra superior **no** va aqui aunque visualmente la corone: se pinta en la
 * pagina, arriba de este componente, y flota `fixed` sobre el video — por eso
 * el video puede llegar hasta el borde real de arriba sin dejarle un hueco.
 *
 * Es un Server Component: lo unico que necesita JavaScript es la barra de
 * reserva, su propia isla de cliente.
 */
export function Hero({ lang, dict, minDate }: HeroProps) {
  const facts = [
    dict.about.facts.duration,
    dict.about.facts.departure,
    dict.about.facts.capacity,
    dict.about.facts.season,
  ];

  return (
    // z-10 para que los paneles de la barra (calendario, hora) queden por encima
    // de las secciones que vienen despues en el DOM.
    <section id="inicio" className="relative z-10 bg-background">
      {/* La altura se mide contra la ventana y no en pixeles fijos: la barra de
          reserva monta sobre el borde de abajo de la foto, y con 640px fijos caia
          fuera de pantalla en cualquier laptop de 720-800px de alto. Se topa en
          520px para que en un monitor grande la foto no crezca sin control.

          `--nav-alto` se le suma **a los dos**, al alto minimo y al `pt` de
          abajo, y esa es la parte que no es obvia. La barra ya no ocupa lugar
          en el flujo (es `fixed`, para que el video llegue hasta el borde real
          de arriba), asi que el hueco que dejaba hay que reponerlo; pero cual
          de las dos medidas manda depende del alto de la ventana. El bloque de
          texto es `justify-end`: si sobra sitio se pega abajo y el aire de
          arriba lo pone el alto minimo, y si no sobra la caja crece con el
          contenido y el aire lo pone el `pt`. Subir una sola de las dos
          arregla la mitad de las ventanas y en la otra mitad no mueve nada
          — que es exactamente lo que paso al intentarlo con el alto minimo
          solo. Subiendo las dos, el titular queda donde estaba siempre, y
          todo lo que antes era el fondo blanco de la barra ahora es video.

          Es `min-height` y no `height`: el titular vive en el flujo, no clavado
          al fondo con `absolute`. Con altura fija y texto absoluto, un titular
          de tres renglones crecia hacia arriba hasta pegarse a la barra
          superior. Asi la foto se estira si el texto lo necesita y el aire de
          arriba esta siempre. */}
      <div className="relative w-full overflow-hidden">
        {/* Decorativo: es el fondo detras del titular, que ya dice de que va el
            sitio. `poster` evita el cuadro en blanco mientras el video (pesado)
            termina de cargar. */}
        <video
          autoPlay
          muted
          loop
          playsInline
          poster="/photos/cola-amarilla-acantilado.webp"
          className="absolute inset-0 h-full w-full object-cover"
        >
          <source src="/videos/videohero.webm" type="video/webm" />
        </video>
        {/* El texto nunca va directo sobre la foto: siempre sobre un degradado. */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, rgba(10,11,14,0.88) 0%, rgba(10,11,14,0.42) 44%, rgba(10,11,14,0.10) 100%)',
          }}
        />

        {/* `justify-end` deja el bloque abajo cuando sobra sitio —la foto se lee
            de arriba abajo y el texto pesa al pie— y lo empuja hacia arriba solo
            si el titular no cabe, respetando siempre el aire de arriba. */}
        <div className="relative flex min-h-[calc(52svh_+_var(--nav-alto))] flex-col justify-end lg:min-h-[calc(min(56svh,520px)_+_var(--nav-alto))]">
          <div className="mx-auto w-full max-w-6xl px-6 pt-[calc(5rem_+_var(--nav-alto))] pb-10 sm:px-8 lg:px-12 lg:pt-[calc(7rem_+_var(--nav-alto))] lg:pb-16">
            <h1 className="titulo-entra max-w-[19ch] text-[38px] leading-[1.02] text-hero-ink sm:text-6xl lg:text-[76px] lg:leading-[0.98]">
              {dict.hero.headlineStart} <span className="acento">{dict.hero.headlineEmphasis}</span>{' '}
              {dict.hero.headlineEnd}
            </h1>
            <p className="titulo-entra titulo-entra-tarde mt-5 max-w-[52ch] text-base leading-relaxed text-hero-ink-soft lg:mt-6 lg:text-lg">
              {dict.hero.subtext}
            </p>
          </div>
        </div>
      </div>

      {/* Monta sobre la foto: la barra pertenece a la foto, no a lo que sigue.
          El `id` no es decoracion: es lo que vigila StickyBookingBar para saber
          cuando esta barra se fue de cuadro y toca sacar la de abajo. */}
      <div
        id={ID_BARRA_PORTADA}
        className="relative mx-auto -mt-8 max-w-6xl px-6 sm:px-8 lg:-mt-12 lg:max-w-4xl lg:px-12"
      >
        <BookingBar lang={lang} booking={dict.booking} minDate={minDate} />
      </div>

      <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-6 pt-12 pb-16 sm:px-8 lg:grid-cols-4 lg:gap-x-0 lg:px-12 lg:pt-14 lg:pb-20">
        {facts.map(({ value, label }, i) => (
          <div
            key={label}
            className={`flex flex-col gap-1 lg:px-8 ${
              i === 0 ? 'lg:pl-0' : 'lg:border-l lg:border-border'
            } ${i === 3 ? 'lg:pr-0' : ''}`}
          >
            <dt className="text-xl font-bold tracking-[-0.02em] text-accent lg:text-[23px]">
              {value}
            </dt>
            <dd className="text-sm text-muted">{label}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
