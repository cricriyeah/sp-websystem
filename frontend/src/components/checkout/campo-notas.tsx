'use client';

import type { Dictionary } from '@/app/[lang]/dictionaries';
import { AreaTexto } from '@/components/ui/area-texto';
import { NOTAS_MAX } from '@/lib/notas';

type Props = {
  idPrefijo: string;
  textos: Dictionary['checkout']['notas'];
  /** Si el viaje sale al mar, la nota es «para tu capitán»; si no, para la empresa. */
  alMar: boolean;
  /** En un paquete la leen todas sus empresas. */
  paquete?: boolean;
  valor: string;
  disabled?: boolean;
  onCambio: (valor: string) => void;
};

/**
 * La nota opcional para quien lleva al cliente (pedido del dueño, 2026-11-16, como la de los marketplaces de
 * pesca). Va al final de «Tus datos», después de lo obligatorio, y nunca detiene el paso: vacía está bien. El
 * ejemplo dice qué escribir (primera vez, una celebración, una alergia) y la ayuda, quién lo va a leer.
 */
export function CampoNotas({ idPrefijo, textos, alMar, paquete, valor, disabled, onCambio }: Props) {
  const id = `${idPrefijo}-notas`;
  const restantes = NOTAS_MAX - valor.length;
  return (
    <div className="flex flex-col gap-1.5 pt-5 text-base sm:text-sm">
      <label htmlFor={id} className="flex items-baseline justify-between gap-3">
        <span className="text-muted">{alMar ? textos.tituloMar : textos.titulo}</span>
        <span className="texto-pequeno text-muted">{textos.opcional}</span>
      </label>
      <AreaTexto
        id={id}
        rows={3}
        maxLength={NOTAS_MAX}
        value={valor}
        disabled={disabled}
        placeholder={textos.ejemplo}
        aria-describedby={`${id}-ayuda`}
        onChange={(e) => onCambio(e.target.value)}
      />
      <p id={`${id}-ayuda`} className="flex flex-wrap justify-between gap-x-4 gap-y-1 texto-pequeno text-muted">
        <span>{paquete ? textos.ayudaPaquete : textos.ayuda}</span>
        {restantes <= 100 && <span aria-live="polite">{textos.restantes.replace('{n}', String(restantes))}</span>}
      </p>
    </div>
  );
}
