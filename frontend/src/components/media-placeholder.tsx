type MediaPlaceholderProps = {
  /** Que foto/video va aqui. Se muestra debajo: sirve de lista de tomas. */
  hint: string;
  aspect?: 'video' | 'square' | 'portrait' | 'wide' | 'card' | 'fill';
  /** Oculta el pie. Solo para huecos que ya viven dentro de una banda con texto. */
  showHint?: boolean;
  className?: string;
};

const PROPORCIONES = {
  video: 'aspect-video',
  square: 'aspect-square',
  portrait: 'aspect-[3/4]',
  wide: 'aspect-[21/9]',
  card: 'aspect-[4/3]',
  // Para bandas a sangre donde la altura la pone el contenedor.
  fill: 'h-full',
};

/**
 * Cuatro tonos fotograficos, desaturados y oscuros. Se reparten de forma
 * determinista por el texto de la toma para que una galeria no se vea como seis
 * bloques identicos, y para que servidor y cliente pinten siempre lo mismo.
 */
const TONOS = [
  'linear-gradient(150deg, #1e252c 0%, #38424c 55%, #232a31 100%)',
  'linear-gradient(200deg, #29323a 0%, #414b55 48%, #262d34 100%)',
  'linear-gradient(130deg, #222931 0%, #363f49 50%, #1f262c 100%)',
  'linear-gradient(165deg, #262d34 0%, #3c454e 50%, #222930 100%)',
];

function tonoDe(texto: string) {
  let suma = 0;
  for (let i = 0; i < texto.length; i += 1) suma = (suma + texto.charCodeAt(i)) % 1024;
  return TONOS[suma % TONOS.length];
}

/**
 * Hueco para material que todavia no existe.
 *
 * **No es un elemento de diseno, y esa es la decision.** Antes era una tarjeta
 * con borde punteado e icono de camara, o sea decoracion que al llegar las fotos
 * habria que desmontar. Ahora es un tono fotografico neutro: se lee como una
 * foto que aun no carga, y la maqueta no se mueve cuando se sustituya por un
 * `<Image>` con el mismo encuadre.
 *
 * La descripcion de la toma va **debajo**, como pie, nunca encima de la imagen.
 * Sigue sirviendo de lista de pendientes para quien las va a tomar.
 */
export function MediaPlaceholder({
  hint,
  aspect = 'video',
  showHint = true,
  className = '',
}: MediaPlaceholderProps) {
  return (
    <figure className={`flex min-w-0 flex-col ${aspect === 'fill' ? 'h-full' : ''} ${className}`}>
      <div
        className={`w-full ${PROPORCIONES[aspect]}`}
        style={{ background: tonoDe(hint) }}
        role="img"
        aria-label={hint}
      />
      {showHint ? (
        <figcaption className="mt-2 text-xs leading-relaxed text-muted">{hint}</figcaption>
      ) : null}
    </figure>
  );
}
