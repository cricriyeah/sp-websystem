import Image from 'next/image';
import { cn } from './cn';
import { iniciales } from '@/lib/iniciales';

/**
 * Quién es quién: el logo de la empresa o, si no hay, su monograma, siempre en
 * círculo. Server Component: no recibe estado, solo lo que ya se sabe de la empresa.
 * Como `ui/` no puede importar `content/`, el nombre y el logo llegan por prop desde
 * la página (servidor).
 *
 * El sello es decorativo: la identidad es el nombre en texto. Por eso, con
 * `mostrarNombre` el sello va oculto a lectores y sin `alt`; sin él, el sello es la
 * única señal y lleva el nombre. NUNCA lleva un color por empresa: azul, coral y
 * verde son de actividad.
 */
type Tamano = 24 | 32 | 64;

const CIRCULO: Record<Tamano, string> = { 24: 'size-6', 32: 'size-8', 64: 'size-16' };
// Letra al 40 % del círculo en 32 y 64. A 24 el 40 % (9,6 px) queda bajo el mínimo
// de 12 px: solo la inicial, en texto-pie.
const LETRA: Record<Tamano, string> = { 24: 'texto-pie', 32: 'text-[12.8px] leading-none', 64: 'text-[25.6px] leading-none' };
const NOMBRE: Record<Tamano, string> = {
  24: 'texto-etiqueta text-foreground',
  32: 'texto-etiqueta text-foreground',
  64: 'texto-paso text-foreground',
};

type EmpresaSelloProps = {
  nombre: string;
  logo?: string | null;
  tamano: Tamano;
  /** Pinta el nombre junto al sello. */
  mostrarNombre?: boolean;
  className?: string;
};

export function EmpresaSello({ nombre, logo, tamano, mostrarNombre = false, className }: EmpresaSelloProps) {
  const letras = tamano === 24 ? iniciales(nombre).slice(0, 1) : iniciales(nombre);

  const sello = logo ? (
    <span className={cn('relative shrink-0 overflow-hidden rounded-full border border-borde bg-blanco', CIRCULO[tamano])}>
      <Image
        src={logo}
        alt={mostrarNombre ? '' : nombre}
        fill
        sizes={`${tamano}px`}
        className="object-contain p-[12%]"
      />
    </span>
  ) : (
    <span
      {...(mostrarNombre ? { 'aria-hidden': true } : { role: 'img', 'aria-label': nombre })}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-cafe-bruma font-display font-bold text-cafe-profundo',
        CIRCULO[tamano],
        LETRA[tamano],
      )}
    >
      {letras}
    </span>
  );

  if (!mostrarNombre) return className ? <span className={cn('inline-flex', className)}>{sello}</span> : sello;

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      {sello}
      <span className={NOMBRE[tamano]}>{nombre}</span>
    </span>
  );
}
