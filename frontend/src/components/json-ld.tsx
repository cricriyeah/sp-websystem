/** JSON dentro de <script>: `<` se escapa para que un texto no pueda cerrar la etiqueta (guía json-ld de Next). */
export const aJsonLd = (dato: unknown) => JSON.stringify(dato).replace(/</g, '\\u003c');

/** Uno o varios bloques de datos estructurados para Google. Sin datos no pinta nada. */
export function JsonLd({ datos }: { datos: unknown | unknown[] | null | undefined }) {
  if (!datos) return null;
  const bloques = Array.isArray(datos) ? datos : [datos];
  return (
    <>
      {bloques.map((bloque, i) => (
        <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{ __html: aJsonLd(bloque) }} />
      ))}
    </>
  );
}
