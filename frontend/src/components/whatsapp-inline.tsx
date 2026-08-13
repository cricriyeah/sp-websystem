import { WhatsappLogo } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

type WhatsappInlineProps = {
  nav: Dictionary['nav'];
  label: string;
  /** Mensaje prellenado. Por defecto, el general de reservas. */
  mensaje?: string;
  className?: string;
};

/**
 * Enlace de WhatsApp para meter dentro del contenido, no en la barra.
 *
 * Se usa donde alguien podria atorarse (la licencia, un grupo grande, una duda
 * de temporada): ahi es donde vale mas poder preguntarle a una persona. Si no
 * hay numero configurado no se pinta, igual que el de la barra.
 */
export function WhatsappInline({ nav, label, mensaje, className = '' }: WhatsappInlineProps) {
  if (!tieneWhatsapp) return null;

  return (
    <a
      href={whatsappHref(mensaje ?? nav.whatsappMessage)}
      target="_blank"
      rel="noopener"
      className={`inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition-transform hover:scale-[1.02] active:scale-[0.98] ${className}`}
    >
      <WhatsappLogo size={18} weight="fill" />
      {label}
    </a>
  );
}
