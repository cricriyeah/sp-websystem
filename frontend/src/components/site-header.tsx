'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { WhatsappContact } from '@/components/whatsapp-contact';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** Clases extra del `<header>`. Existe para el `print:hidden` del recibo. */
  className?: string;
};

/**
 * Barra superior, una sola linea y siempre sobre papel.
 *
 * Antes tenia dos tonos porque en la portada flotaba sobre un degradado
 * turquesa. En el rediseno la portada arranca con una foto a sangre **debajo**
 * de la barra, asi que la barra es blanca en todas las paginas y la distincion
 * dejo de existir.
 */
export function SiteHeader({ lang, nav, className = '' }: SiteHeaderProps) {
  const [open, setOpen] = useState(false);
  const sinMovimiento = useReducedMotion();

  // Absolutos y no anclas sueltas: desde el checkout o el deslinde, un `#nosotros`
  // no llevaria a ningun lado porque esas secciones viven en la portada.
  const links = [
    { href: `/${lang}#temporadas`, label: nav.temporadas },
    { href: `/${lang}#nosotros`, label: nav.nosotros },
    { href: `/${lang}#galeria`, label: nav.galeria },
    { href: `/${lang}#preguntas`, label: nav.preguntas },
  ];

  return (
    // `sticky`: la barra se queda arriba al bajar. Es la unica via permanente a
    // reservar y a WhatsApp, y el sitio es una pagina larga de una sola tirada:
    // si se va con el scroll, volver a ella obliga a subir hasta el principio.
    // Va sobre `bg-background` opaco a proposito y no translucida — abajo pasa
    // una foto a sangre, y el texto de la barra sobre ella no se leeria.
    <header
      className={`sticky top-0 z-40 shrink-0 border-b border-border bg-background ${className}`}
    >
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between gap-6 px-6 sm:px-8 lg:h-[88px] lg:px-12">
        {/* Solo el logo, sin el nombre al lado. Por eso el `alt` lleva la marca
            completa y no va vacio: es lo unico que identifica al sitio aqui, y
            con `alt=""` un lector de pantalla anunciaria un enlace sin nombre. */}
        <Link
          href={`/${lang}`}
          className="flex shrink-0 items-center text-foreground"
          onClick={() => setOpen(false)}
        >
          {/* `priority`: es lo primero que se ve del sitio y va en todas las
              paginas; a carga diferida entraria tarde, con un salto. */}
          <Image
            src="/logos/logo2salysol.png"
            alt={`${nav.brandMain} ${nav.brandAccent}`}
            width={1026}
            height={331}
            priority
            className="h-11 w-auto lg:h-14"
          />
        </Link>

        <nav className="hidden items-center gap-7 lg:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[15px] text-foreground transition-colors hover:text-accent"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <WhatsappContact nav={nav} tone="plain" />

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className="flex h-11 w-11 items-center justify-center border border-border text-foreground lg:hidden"
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            key="menu-movil"
            initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            // `absolute`: sin esto el menu vivia en el flujo normal del
            // `<header>` (que es `sticky`, no `fixed`) y al abrirse empujaba
            // hacia abajo todo el contenido de la pagina en vez de montarse
            // encima. `top-full` lo cuelga justo debajo de la barra, y la
            // sombra le da separacion visual contra lo que tapa.
            className="absolute inset-x-0 top-full flex flex-col border-t border-border bg-surface px-6 py-2 shadow-[0_16px_40px_rgba(11,36,32,0.18)] sm:px-8 lg:hidden"
          >
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="border-b border-border-strong py-3.5 text-[15px] text-foreground last:border-b-0"
              >
                {link.label}
              </Link>
            ))}
            <div className="py-3">
              <WhatsappContact nav={nav} variant="menu" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
