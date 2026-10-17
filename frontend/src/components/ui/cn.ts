import { clsx, type ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

// Los tokens propios no son tallas de Tailwind: sin esto twMerge los trata como
// clases sin conflicto y un `className` externo no puede sustituirlos.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      rounded: [{ rounded: ['control', 'campo', 'card', 'sheet', 'casilla'] }],
      'rounded-t': [{ 'rounded-t': ['sheet'] }],
      shadow: [{ shadow: ['n0', 'n1', 'n2'] }],
    },
  },
});

export function cn(...entradas: ClassValue[]) {
  return twMerge(clsx(entradas));
}
