import { WhatsappLogo } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { tieneWhatsapp, whatsappHref, whatsappVisible } from '@/lib/contacto';

type WhatsappContactProps = {
  nav: Dictionary['nav'];
  /** `nav` va en la barra superior; `menu` es el bloque del menu movil. */
  variant?: 'nav' | 'menu';
  /** Solo cambia el color de la frase, que va sobre fondos distintos. */
  tone?: 'hero' | 'plain';
};

/**
 * Contacto humano por WhatsApp, para quien no quiere reservar en linea.
 *
 * No es un boton a un formulario: muestra el numero real y abre la conversacion
 * con el mensaje ya escrito, para que el cliente solo tenga que darle enviar.
 *
 * Si no hay `NEXT_PUBLIC_WHATSAPP_NUMBER` configurado no se pinta nada — es
 * preferible a publicar un numero de relleno (ver src/lib/contacto.ts).
 */
export function WhatsappContact({ nav, variant = 'nav', tone = 'hero' }: WhatsappContactProps) {
  if (!tieneWhatsapp) return null;

  const href = whatsappHref(nav.whatsappMessage);
  const numero = whatsappVisible();

  if (variant === 'menu') {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener"
        className="mt-1 flex flex-col gap-1 bg-accent px-4 py-3 text-accent-foreground"
      >
        <span className="text-xs opacity-90">{nav.humanContact}</span>
        <span className="flex items-center gap-2 text-sm font-medium">
          <WhatsappLogo size={18} weight="fill" />
          {numero}
        </span>
      </a>
    );
  }

  return (
    <div className="hidden items-center gap-3 lg:flex">
      {/* La frase se cae en pantallas medianas; el numero nunca. */}
      <span
        className={`hidden text-sm xl:inline ${tone === 'hero' ? 'text-hero-ink-soft' : 'text-muted'}`}
      >
        {nav.humanContact}
      </span>
      <a
        href={href}
        target="_blank"
        rel="noopener"
        aria-label={`${nav.whatsappCta}: ${numero}`}
        className="flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition-transform hover:scale-[1.02] active:scale-[0.98]"
      >
        <WhatsappLogo size={18} weight="fill" />
        {numero}
      </a>
    </div>
  );
}
