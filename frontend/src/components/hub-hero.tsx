'use client';

type HubHeroProps = {
  nombreAgencia: string;
  mision: string;
  ctaLabel: string;
  mapaAnchorId: string;
};

export function HubHero({ nombreAgencia, mision, ctaLabel, mapaAnchorId }: HubHeroProps) {
  return (
    <section className="relative overflow-hidden bg-background">
      <div className="relative min-h-[70svh]">
        {/* eslint-disable-next-line @next/next/no-img-element -- fondo decorativo a sangre */}
        <img
          src="/photos/yellowtail-pelicanos-bahia.webp"
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, rgba(10,11,14,0.88) 0%, rgba(10,11,14,0.42) 44%, rgba(10,11,14,0.10) 100%)',
          }}
        />
        <div className="relative mx-auto flex min-h-[70svh] max-w-6xl flex-col justify-end px-6 pb-16 pt-[calc(6rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
          <h1 className="max-w-[20ch] text-[38px] leading-[1.02] text-hero-ink sm:text-6xl lg:text-[72px] lg:leading-[0.98]">
            {nombreAgencia}
          </h1>
          <p className="mt-5 max-w-[52ch] text-base leading-relaxed text-hero-ink-soft lg:text-lg">
            {mision}
          </p>
          <button
            type="button"
            onClick={() => document.getElementById(mapaAnchorId)?.scrollIntoView({ behavior: 'smooth' })}
            className="mt-8 inline-flex w-fit items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-semibold text-white shadow-md transition-transform hover:brightness-105 active:scale-[0.98]"
          >
            {ctaLabel}
          </button>
        </div>
      </div>
    </section>
  );
}
