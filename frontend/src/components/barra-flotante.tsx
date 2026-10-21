import Image from 'next/image';
import type { CSSProperties, ReactNode } from 'react';
import { X } from '@phosphor-icons/react/ssr';
import { cn } from '@/components/ui/cn';

const MARCA = 'Sun Baja Experience';

type BarraFlotanteProps = {
  /** Lo primero de la barra, pegado a la izquierda: aparece desde el primer cuadro (el círculo de partida). */
  inicio: ReactNode;
  /** El resto de la barra: aparece cuando el fondo ya casi llegó al otro extremo. */
  resto: ReactNode;
  /** Lo que cuelga bajo la barra (menú móvil), ya posicionado respecto de ella. */
  menu?: ReactNode;
  /** La banda que va pegada debajo de la barra (continuar reservación). */
  debajo?: ReactNode;
  /** Clases extra del contenedor fijo. Existe para el `print:hidden` del recibo. */
  className?: string;
};

/**
 * La barra superior del sitio y del checkout (F10): una píldora flotante blanca, igual
 * en móvil y en escritorio. Al cargar, el fondo nace como un círculo del tamaño del logo y se
 * expande hacia la derecha mientras el contenido aparece dentro (ver `.barra-fondo` y `.barra-resto`
 * en globals.css). El fondo es un hijo aparte que se revela con `clip-path` (sin tocar el layout
 * ni recortar con `overflow` lo que se despliega fuera de la barra: selectores, menú); la sombra, otro
 * hijo quieto que aparece al final.
 *
 * Alto: `--barra-h` (64 px en móvil, 72 en escritorio) más el margen de arriba; `--nav-alto` (globals.css) lo suma. Server Component: lo que necesita estado llega ya armado en `inicio`, `resto` y `menu`.
 */
export function BarraFlotante({ inicio, resto, menu, debajo, className }: BarraFlotanteProps) {
  return (
    <div className={cn('fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-6 lg:px-8 lg:pt-4', className)}>
      <div className="relative mx-auto flex w-full flex-col lg:max-w-[1440px]">
        <header className="relative flex h-[var(--barra-h)] items-center gap-4 px-4 sm:px-5 lg:px-7">
          <span aria-hidden="true" className="barra-sombra absolute inset-0 rounded-full shadow-n2" />
          <span aria-hidden="true" className="barra-fondo absolute inset-0 rounded-full bg-superficie" />
          <div className="relative flex shrink-0 items-center">{inicio}</div>
          <div className="barra-resto relative flex min-w-0 flex-1 items-center justify-between gap-3 lg:gap-5">{resto}</div>
        </header>
        {menu}
        {debajo}
      </div>
    </div>
  );
}

type LogoMarcaProps = {
  /** `true` gira el logo media vuelta (el menú móvil lo usa al abrirse; al cerrarse vuelve hacia la izquierda). */
  girado?: boolean;
  /** Milisegundos que espera el giro de entrada: el checkout lo retrasa hasta que su barra ya se abrió. */
  retraso?: number;
};

/**
 * Nuestra marca: el logo redondo de Sun Baja Experience, sin recuadro. Gira media vuelta al cargar la
 * página (`.logo-gira`) y, con `girado`, otra media vuelta al abrir el menú: la transición vuelve por el
 * mismo camino, o sea hacia la izquierda, al cerrarlo. Dos capas porque el giro de carga es una
 * animación y el del menú una transición, y las dos usan `transform`.
 */
export function LogoMarca({ girado = false, retraso = 0 }: LogoMarcaProps) {
  const estilo: CSSProperties | undefined = retraso ? { animationDelay: `${retraso}ms` } : undefined;
  return (
    <span className="logo-gira inline-flex" style={estilo}>
      <span
        className={cn(
          'inline-flex transition-transform duration-[900ms] ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none',
          girado && 'rotate-180',
        )}
      >
        <Image src="/sunbajaexperience/logosm.svg" alt={MARCA} width={44} height={44} className="size-11" priority />
      </span>
    </span>
  );
}

type LogosProps = {
  /** La empresa protagonista de la sede: va junto a nuestra marca, separada por una equis. */
  empresa?: { nombre: string; logo?: string };
  /** Bajo 640 px no se pinta: la barra del checkout lleva además el botón de atención al cliente y no cabe todo. */
  ocultoEnMovil?: boolean;
};

/**
 * La empresa que acompaña a la marca: su logo suelto (sin círculo ni borde) detrás de una equis, o
 * su nombre en texto si todavía no tiene logo. Nunca iniciales: el nombre es la identidad.
 */
export function LogoEmpresaAlLado({ empresa, ocultoEnMovil = false }: LogosProps) {
  if (!empresa) return null;
  return (
    <div className={cn('flex min-w-0 items-center gap-3', ocultoEnMovil && 'max-sm:hidden')}>
      <X aria-hidden="true" size={14} weight="bold" className="shrink-0 text-foreground" />
      {empresa.logo ? (
        <Image
          src={empresa.logo}
          alt={empresa.nombre}
          width={120}
          height={36}
          className="h-8 w-auto max-w-[7.5rem] shrink-0 object-contain sm:h-9"
        />
      ) : (
        <span className="truncate texto-etiqueta">{empresa.nombre}</span>
      )}
    </div>
  );
}
