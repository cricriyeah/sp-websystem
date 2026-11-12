'use client';

import { useEffect } from 'react';
import { EVENTO_CONSENTIMIENTO, leerConsentimiento } from '@/lib/cookies';
import { PERFIL_TRIPADVISOR_MARCA } from '@/content/redes-marca';

/**
 * Insignia «rated» de TripAdvisor del pie (código del dueño, 2026-11-12; locationId 34807297, uniq 819).
 *
 * Sin script se ve la insignia fija de TripAdvisor con su enlace a la ficha: es el marcado que pegó el dueño. Con
 * las cookies aceptadas se carga el script de TripAdvisor, que cambia ese marcado por la insignia con la
 * calificación. Va detrás del consentimiento como el pixel: es un tercero que carga código y estilos.
 *
 * El código del dueño carga `jscache.com/wejs`, que solo inserta `WidgetEmbed-rated`; aquí se carga ese directo.
 * Ese script se cuelga de `window.onload`, que en un sitio de Next ya pasó cuando llega: por eso, al cargar, se
 * llama a mano `window.taValidate`, que pinta la insignia dentro de `#TA_rated819`. Al volver a montar el pie en
 * otra página el script ya está: se vuelve a llamar y reemplaza el contenido del contenedor nuevo.
 *
 * El marcado va con `dangerouslySetInnerHTML` para que React no reconcilie lo que el script reescribe.
 */
const SCRIPT_ID = 'tripadvisor-rated-819';
const SCRIPT_SRC =
  'https://www.tripadvisor.com.mx/WidgetEmbed-rated?lang=es_MX&locationId=34807297&display_version=2&uniq=819';

const MARCADO =
  '<ul id="mmoTdv3y1" class="TA_links yK7l0af0iX6K"><li id="SRnAJP4N" class="hM87KXrQg">' +
  `<a target="_blank" rel="noopener" href="${PERFIL_TRIPADVISOR_MARCA}">` +
  '<img src="https://www.tripadvisor.com.mx/img/cdsi/img2/badges/ollie-11424-2.gif" alt="TripAdvisor"/>' +
  '</a></li></ul>';

type VentanaTripadvisor = Window & { taValidate?: () => void };

function pintar() {
  try {
    (window as VentanaTripadvisor).taValidate?.();
  } catch {
    // Si TripAdvisor falla, queda la insignia fija.
  }
}

function cargarScript() {
  if (document.getElementById(SCRIPT_ID)) {
    pintar();
    return;
  }
  const script = document.createElement('script');
  script.id = SCRIPT_ID;
  script.src = SCRIPT_SRC;
  script.async = true;
  script.onload = pintar;
  document.body.appendChild(script);
}

export function InsigniaTripadvisor() {
  useEffect(() => {
    if (leerConsentimiento() === 'aceptado') {
      cargarScript();
      return;
    }
    const alAceptar = () => {
      if (leerConsentimiento() === 'aceptado') cargarScript();
    };
    window.addEventListener(EVENTO_CONSENTIMIENTO, alAceptar);
    return () => window.removeEventListener(EVENTO_CONSENTIMIENTO, alAceptar);
  }, []);

  return <div id="TA_rated819" className="TA_rated" dangerouslySetInnerHTML={{ __html: MARCADO }} />;
}
