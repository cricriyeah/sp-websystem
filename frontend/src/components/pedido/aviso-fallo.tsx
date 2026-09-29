import { WhatsappLogo } from '@phosphor-icons/react';

type Props = {
  titulo: string;
  /** Por qué falló, ya traducido. Null cuando no se sabe (p. ej. tras recargar la página). */
  motivo: string | null;
  /** Qué pasó con el dinero. Va antes que cualquier otra cosa que se le pida al cliente. */
  lineasDinero: string[];
  etiquetaBoton: string;
  onReintentar: () => void;
  ayuda: { etiqueta: string; href: string } | null;
};

export function AvisoFallo({ titulo, motivo, lineasDinero, etiquetaBoton, onReintentar, ayuda }: Props) {
  return (
    <div role="alert" className="rounded-xl border border-border bg-card p-5">
      <h1 className="text-lg font-semibold text-foreground sm:text-xl">{titulo}</h1>
      {motivo && <p className="mt-1 text-sm text-foreground">{motivo}</p>}
      <div className="mt-3 flex flex-col gap-2 text-xs leading-relaxed text-muted">
        {lineasDinero.map((linea) => <p key={linea}>{linea}</p>)}
      </div>
      <button type="button" onClick={onReintentar}
        className="mt-5 w-full rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground">
        {etiquetaBoton}
      </button>
      {ayuda && (
        <a href={ayuda.href} target="_blank" rel="noopener"
          className="mt-3 flex items-center justify-center gap-2 text-sm font-medium text-muted hover:text-foreground">
          <WhatsappLogo size={18} weight="fill" />
          {ayuda.etiqueta}
        </a>
      )}
    </div>
  );
}
