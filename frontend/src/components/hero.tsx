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

  const container = {
    hidden: {},
    show: {
      transition: { staggerChildren: reduce ? 0 : 0.12, delayChildren: reduce ? 0 : 0.1 },
    },
  };

  const item = {
    hidden: reduce ? {} : { opacity: 0, y: 18 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const },
    },
  };

  return (
    <section id="inicio" className="bg-background">
      <div className="relative flex min-h-[100dvh] flex-col overflow-hidden">
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
