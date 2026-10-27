// Módulo puro, SIN imports (lo compila el runner de pruebas).

/**
 * Dónde vive en el bucket de Cloudflare R2 cada video del sitio. La llave es la ruta con la que el
 * contenido nombra el video (`/videos/archivo`, que sigue siendo un archivo de `public/videos`) y el
 * valor es su ruta dentro del bucket, que va en carpetas por sede. Un video que no esté aquí se
 * sigue sirviendo desde `public`.
 */
const VIDEOS_EN_BUCKET: Record<string, string> = {
  '/videos/videohub.webm': 'hub/videohub.webm',
  '/videos/videonuevonuevolapaz.mp4': 'lapaz/videonuevonuevolapaz-20s.mp4',
  '/videos/ventana-hero.webm': 'laventana/videolaventana-0025-0045.mp4',
};

/**
 * Dirección de un video del sitio. Con `base` (el dominio público del bucket, en
 * `NEXT_PUBLIC_MEDIA_BASE_URL`) devuelve la del bucket si el video está en la tabla; sin `base`, o
 * con un video que no esté en la tabla, devuelve la ruta tal cual y se sirve desde `public`.
 */
export function urlVideo(ruta: string, base: string | undefined): string {
  const raiz = base?.trim().replace(/\/+$/, '');
  const enBucket = VIDEOS_EN_BUCKET[ruta];
  if (!raiz || !enBucket) return ruta;
  return `${raiz}/${enBucket}`;
}
