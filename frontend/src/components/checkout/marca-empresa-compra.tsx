import Image from 'next/image';
import type { LogoLargo } from '@/content/empresas-marca';
import { EmpresaSello } from '@/components/ui/empresa-sello';
import { cn } from '@/components/ui/cn';

export type EmpresaDeCompra = { nombre: string; logo?: string; simbolo?: string; simboloBarra?: string; logoLargo?: LogoLargo };

/**
 * La cara de la empresa en el checkout (bajo el título y en el resumen del pedido): su logo largo a color (isotipo y
 * nombre), 48 px de alto, cuando lo tiene (dueño, 2026-11-17: el sello redondo se veía muy chico). Sin logo largo, el
 * sello de 48 px; con `conNombre`, con su nombre al lado (el logo largo ya lo trae dibujado).
 */
export function MarcaEmpresaCompra({ empresa, conNombre = false, className }: { empresa: EmpresaDeCompra; conNombre?: boolean; className?: string }) {
  if (empresa.logoLargo) {
    return (
      <Image
        src={empresa.logoLargo.src}
        alt={empresa.nombre}
        width={empresa.logoLargo.ancho}
        height={empresa.logoLargo.alto}
        className={cn('h-12 w-auto max-w-[10rem] shrink-0 object-contain object-left', className)}
      />
    );
  }
  return (
    <EmpresaSello
      nombre={empresa.nombre}
      logo={empresa.simbolo ?? empresa.simboloBarra ?? empresa.logo}
      tamano={48}
      mostrarNombre={conNombre}
      className={className}
    />
  );
}
