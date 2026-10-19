'use client';

import { useEffect, useState } from 'react';

/** Lo que el teclado le quita al alto visible para darlo por abierto (la barra de Safari mide ~80). */
const UMBRAL_PX = 150;

const esCampoDeTexto = (el: Element | null) =>
  el instanceof HTMLTextAreaElement
  || (el instanceof HTMLInputElement && !['checkbox', 'radio', 'button', 'submit'].includes(el.type));

/**
 * ¿El teclado del teléfono está abierto? Un campo de texto con el foco y el alto visible
 * (`visualViewport`) recortado. Con el teclado abierto la barra fija taparía el campo: la barra
 * pasa a estática al final del contenido mientras tanto. El iframe de Stripe no cuenta: su foco
 * vive en otro documento, y su formulario ya queda arriba de la barra.
 */
export function useTecladoAbierto(): boolean {
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    const vista = window.visualViewport;
    if (!vista) return;
    const revisar = () => {
      setAbierto(esCampoDeTexto(document.activeElement) && window.innerHeight - vista.height > UMBRAL_PX);
    };
    vista.addEventListener('resize', revisar);
    document.addEventListener('focusin', revisar);
    document.addEventListener('focusout', revisar);
    return () => {
      vista.removeEventListener('resize', revisar);
      document.removeEventListener('focusin', revisar);
      document.removeEventListener('focusout', revisar);
    };
  }, []);

  return abierto;
}
