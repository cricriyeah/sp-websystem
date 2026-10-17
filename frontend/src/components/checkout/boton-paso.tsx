import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';

/**
 * El único CTA primario de una tarjeta de paso. Antes había tres formas
 * distintas (redondo con pregunta, redondo suelto, cuadrado con flecha): la
 * misma función se veía diferente en cada paso.
 *
 * Envoltorio de `Button variante="principal"`: se conserva el nombre y las
 * props para no tocar a los llamadores.
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
    <Button variante="principal" onClick={onClick} disabled={disabled} conFlecha={conFlecha}>
      {children}
    </Button>
  );
}
