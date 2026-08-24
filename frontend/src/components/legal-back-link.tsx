'use client';

import type { MouseEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from '@phosphor-icons/react';

type LegalBackLinkProps = {
  label: string;
  /** A donde ir si esta pestaña no tiene de donde regresar. */
  fallbackHref: string;
};

/**
 * "Atrás" de las páginas legales (deslinde, privacidad).
 *
 * A esta página se llega desde el pie del sitio, desde el checkout (el
 * deslinde abre en pestaña nueva) o de un link directo — nunca de un solo
 * lugar. Un `href` fijo solo acierta en el caso para el que se escribió; en
 * los demás manda a alguien a una página que no es la que dejó (por eso el
 * texto tiene que ser genérico, "Atrás", y no prometer un destino concreto).
 *
 * Con historial de verdad en esta pestaña se usa `router.back()`. Sin él
 * (pestaña nueva recién abierta, o se entró por un link externo,
 * `history.length` es 1) se sigue el `href` normal hacia el fallback.
 */
export function LegalBackLink({ label, fallbackHref }: LegalBackLinkProps) {
  const router = useRouter();

  function alVolver(evento: MouseEvent<HTMLAnchorElement>) {
    if (window.history.length > 1) {
      evento.preventDefault();
      router.back();
    }
  }

  return (
    <Link
      href={fallbackHref}
      onClick={alVolver}
      className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
    >
      <ArrowLeft size={16} />
      {label}
    </Link>
  );
}
