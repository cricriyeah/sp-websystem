'use client';

import { motion, useReducedMotion } from 'motion/react';
import { SiteHeader } from '@/components/site-header';
import { BookingBar } from '@/components/booking-bar';
import type { Locale, Dictionary } from '@/app/[lang]/dictionaries';

type HeroProps = {
  lang: Locale;
  dict: Dictionary;
  minDate: string;
};

export function Hero({ lang, dict, minDate }: HeroProps) {
  const reduce = useReducedMotion();

  // El contenido del heroe **no arranca invisible**. Antes entraba desde
  // `opacity: 0` con retraso y escalonado, asi que durante casi un segundo la
  // portada era un degradado en blanco: titular, subtitulo y barra de reserva
  // aparecian los tres despues.
  //
  // Ese segundo es justamente el porton donde se forma el juicio visual del
  // sitio, y se estaba gastando en nada. Ahora el primer pintado ya trae la
  // composicion real y el movimiento se queda en un desplazamiento corto: se
  // conserva la entrada sin pagarla con un cuadro vacio.
  const container = {
    hidden: {},
    show: {
      transition: { staggerChildren: reduce ? 0 : 0.07 },
    },
  };

  const item = {
    hidden: reduce ? {} : { y: 14 },
    show: {
      y: 0,
      transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] as const },
    },
  };

  return (
    // z-10 para que los paneles del booking bar (calendario, hora) queden por
    // encima de las secciones que vienen despues en el DOM.
    <section id="inicio" className="relative z-10 bg-background">
      {/* Sin overflow-hidden: recortaria esos paneles. Los degradados de abajo
          son `inset-0`, no se salen del contenedor, asi que no hace falta. */}
      <div className="relative flex min-h-[100dvh] flex-col">
        {/* TODO: replace with real photography of the fleet leaving Marina La Costa at sunrise. */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(178deg, #eef8f7 0%, #c2e8e6 16%, #86d5d6 38%, #43aeb4 66%, #1c858c 100%)',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(circle at 50% 4%, rgba(255,238,196,0.9), rgba(255,238,196,0) 42%)',
          }}
        />

        <SiteHeader lang={lang} nav={dict.nav} />

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col items-center justify-center px-6 py-12 text-center sm:px-8 lg:px-12"
        >
          <motion.h1
            variants={item}
            className="max-w-3xl pb-1 text-4xl leading-[1.15] font-medium tracking-tight text-hero-ink sm:text-5xl lg:text-6xl"
          >
            {dict.hero.headlineStart} <em className="italic">{dict.hero.headlineEmphasis}</em>{' '}
            {dict.hero.headlineEnd}
          </motion.h1>

          <motion.p
            variants={item}
            className="mt-6 max-w-xl text-base text-hero-ink-soft sm:text-lg"
          >
            {dict.hero.subtext}
          </motion.p>

          <motion.div variants={item} className="mt-10 w-full max-w-3xl">
            <BookingBar lang={lang} booking={dict.booking} minDate={minDate} />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
