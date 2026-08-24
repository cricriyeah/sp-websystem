import { Fragment } from 'react';

/**
 * Los textos legales del sitio —aviso de privacidad y deslinde— en prosa.
 *
 * Viven en los diccionarios como un solo string por apartado y no como una
 * estructura, porque son documentos que se reemplazan enteros: cuando cambia la
 * ley o el abogado manda otra version, se pega el texto nuevo y ya. Modelarlos
 * campo por campo obligaria a migrar el diccionario cada vez.
 *
 * A cambio, aqui se interpretan tres marcas y ninguna mas:
 *
 * - Linea en blanco = parrafo nuevo. Los incisos numerados de un contrato (1.1,
 *   3.3, 7.2) tienen que verse como incisos; fundidos en un ladrillo el cliente
 *   no puede seguir lo que esta aceptando.
 * - Lineas que empiezan con `- ` = lista. Un aviso de privacidad enumera
 *   —que datos, para que, cuanto tiempo— y esa enumeracion es la mitad de lo
 *   que hace el documento legible.
 * - `**texto**` = negrita, para la entradilla de cada punto de una lista.
 *
 * No es Markdown ni pretende serlo: es el minimo que estos dos documentos usan.
 */
export function TextoLegal({ texto }: { texto: string }) {
  const bloques = texto.split(/\n\n/);

  return (
    <div className="flex max-w-[65ch] flex-col gap-4">
      {bloques.map((bloque, i) =>
        esLista(bloque) ? (
          <ul key={i} className="flex list-disc flex-col gap-2 pl-5">
            {bloque.split(/\n/).map((linea, j) => (
              <li key={j} className="text-base leading-relaxed text-muted">
                <ConNegritas texto={linea.replace(/^- /, '')} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i} className="text-base leading-relaxed text-muted">
            <ConNegritas texto={bloque} />
          </p>
        )
      )}
    </div>
  );
}

/** Un bloque es lista solo si TODAS sus lineas lo son; asi un guion suelto a
 *  media frase no convierte un parrafo en viñetas. */
function esLista(bloque: string) {
  return bloque.split(/\n/).every((linea) => linea.startsWith('- '));
}

function ConNegritas({ texto }: { texto: string }) {
  // Los impares son lo que iba entre `**`, por como parte un grupo de captura.
  const partes = texto.split(/\*\*(.+?)\*\*/g);

  return (
    <>
      {partes.map((parte, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-medium text-foreground">
            {parte}
          </strong>
        ) : (
          <Fragment key={i}>{parte}</Fragment>
        )
      )}
    </>
  );
}
