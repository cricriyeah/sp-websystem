import type { ReactNode } from 'react';
import { ArrowRight } from '@phosphor-icons/react';

/**
 * El único CTA primario de una tarjeta de paso. Antes había tres formas
 * distintas (redondo con pregunta, redondo suelto, cuadrado con flecha): la
 * misma función se veía diferente en cada paso.
 */
export function BotonPaso({
  children,
  onClick,
  conFlecha = false,
  disabled = false,
}: {
  children: ReactNode;
  onClick: () => void;
  conFlecha?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center gap-2 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98] disabled:opacity-60"
    >
      {children}
      {conFlecha && <ArrowRight size={16} weight="bold" />}
    </button>
  );
}
