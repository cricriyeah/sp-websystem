'use client';

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Check, MagnifyingGlass } from '@phosphor-icons/react';
import { Bandera } from '@/components/ui/bandera';
import { cn } from '@/components/ui/cn';
import { Input } from '@/components/ui/input';
import { buscarPaises, listarPaises, PAISES_FRECUENTES, type PaisTelefono } from '@/lib/paises-telefono';

/** Textos del selector (claves `checkout.*` del diccionario, mismo nombre). */
export type TextosSelectorPais = {
  phoneCountry: string;
  phoneCountrySearch: string;
  phoneCountryNone: string;
  phoneCountryNoneHint: string;
  phoneCountryFrequent: string;
  phoneCountryAll: string;
  /** Lleva `{n}`. */
  phoneCountryCount: string;
  phoneCountryCountOne: string;
};

type Props = {
  lang: string;
  /** Sigla del país elegido. */
  seleccion: string;
  onElegir: (iso: string) => void;
  textos: TextosSelectorPais;
  /** Enfoca el buscador al montar. En la hoja móvil no: el teclado taparía la lista al abrir. */
  enfocar: boolean;
  /** Filas de 48 px (hoja táctil) en lugar de 44. */
  tactil: boolean;
  /** Alto FIJO de la lista: si encogiera al filtrar, el buscador se movería mientras se teclea. */
  claseLista: string;
  /** Tab dentro del panel lo cierra sin elegir. */
  onTab?: () => void;
};

const SALTO = 8;
/** Anuncio del conteo: espera a que el cliente deje de teclear para no leer cada letra. */
const RETRASO_CONTEO_MS = 300;

function useRetrasado<T>(valor: T, ms: number): T {
  const [retrasado, setRetrasado] = useState(valor);
  useEffect(() => {
    const espera = window.setTimeout(() => setRetrasado(valor), ms);
    return () => window.clearTimeout(espera);
  }, [valor, ms]);
  return retrasado;
}

/**
 * Buscador y lista de países del teléfono. Patrón combobox con listbox: el foco se queda en el
 * buscador y la fila activa se anuncia con `aria-activedescendant`. Sin consulta, la lista va en
 * dos grupos (México, Estados Unidos y Canadá, luego el resto sin repetirlos); con consulta, plana.
 * Teclado: flechas (se detienen en los extremos), Re Pág y Av Pág saltan 8, Inicio y Fin con el
 * buscador vacío, Enter elige, Esc lo cierra quien lo contiene (popover u hoja).
 */
export function SelectorPais({ lang, seleccion, onElegir, textos, enfocar, tactil, claseLista, onTab }: Props) {
  const base = useId();
  const idLista = `${base}-lista`;
  const idOpcion = (iso: string) => `${base}-op-${iso}`;
  const entrada = useRef<HTMLInputElement>(null);

  const todos = useMemo(() => listarPaises(lang), [lang]);
  const [consulta, setConsulta] = useState('');
  const frecuentes = useMemo(() => todos.filter((p) => PAISES_FRECUENTES.includes(p.iso)), [todos]);
  const otros = useMemo(() => todos.filter((p) => !PAISES_FRECUENTES.includes(p.iso)), [todos]);
  const resultados = useMemo(() => buscarPaises(todos, consulta), [todos, consulta]);
  const agrupado = consulta.trim() === '';
  const filas = useMemo(() => (agrupado ? [...frecuentes, ...otros] : resultados), [agrupado, frecuentes, otros, resultados]);

  // Al abrir, la fila elegida queda visible y activa.
  const [activo, setActivo] = useState(() => Math.max(0, filas.findIndex((p) => p.iso === seleccion)));
  const [porTeclado, setPorTeclado] = useState(false);

  useEffect(() => {
    if (enfocar) entrada.current?.focus({ preventScroll: true });
  }, [enfocar]);

  const isoActivo = filas[activo]?.iso;
  useEffect(() => {
    if (!isoActivo) return;
    document.getElementById(`${base}-op-${isoActivo}`)?.scrollIntoView({ block: 'nearest', behavior: 'instant' });
  }, [base, isoActivo]);

  const consultaAnunciada = useRetrasado(consulta, RETRASO_CONTEO_MS);
  const anuncio = useMemo(() => {
    if (consultaAnunciada.trim() === '') return '';
    const n = buscarPaises(todos, consultaAnunciada).length;
    return n === 1 ? textos.phoneCountryCountOne : textos.phoneCountryCount.replace('{n}', String(n));
  }, [consultaAnunciada, todos, textos.phoneCountryCount, textos.phoneCountryCountOne]);

  const mover = (indice: number) => {
    setPorTeclado(true);
    setActivo(Math.min(Math.max(0, indice), filas.length - 1));
  };

  const alTeclear = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        mover(activo + 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        mover(activo - 1);
        break;
      case 'PageDown':
        e.preventDefault();
        mover(activo + SALTO);
        break;
      case 'PageUp':
        e.preventDefault();
        mover(activo - SALTO);
        break;
      case 'Home':
        if (consulta === '') {
          e.preventDefault();
          mover(0);
        }
        break;
      case 'End':
        if (consulta === '') {
          e.preventDefault();
          mover(filas.length - 1);
        }
        break;
      case 'Enter': {
        e.preventDefault();
        const fila = filas[activo];
        if (fila) onElegir(fila.iso);
        break;
      }
      case 'Tab':
        onTab?.();
        break;
    }
  };

  const fila = (pais: PaisTelefono) => {
    const elegido = pais.iso === seleccion;
    const esActivo = pais.iso === isoActivo;
    return (
      <div
        key={pais.iso}
        id={idOpcion(pais.iso)}
        role="option"
        aria-selected={elegido}
        // El foco no sale del buscador al tocar una fila.
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => onElegir(pais.iso)}
        className={cn(
          'flex cursor-pointer items-center gap-3 px-3 py-2 text-base transition-colors hover:bg-cafe-bruma sm:text-sm',
          tactil ? 'min-h-12' : 'min-h-11',
          elegido && 'font-medium',
          esActivo && 'bg-cafe-bruma',
          esActivo && porTeclado && 'ring-2 ring-inset ring-tinta',
        )}
      >
        <Bandera iso={pais.iso} tam="m" />
        <span className="min-w-0 flex-1 text-foreground">{pais.nombre}</span>
        <span className="shrink-0 tabular-nums text-muted">+{pais.codigo}</span>
        {/* Columna siempre reservada: elegir no mueve las filas. */}
        <span className="flex size-5 shrink-0 items-center justify-center text-foreground">
          {elegido && <Check size={16} weight="bold" aria-hidden="true" />}
        </span>
      </div>
    );
  };

  const grupo = (id: string, titulo: string, paises: PaisTelefono[]) =>
    paises.length === 0 ? null : (
      <div role="group" aria-labelledby={`${base}-${id}`}>
        <div id={`${base}-${id}`} className="px-3 pt-3 pb-1 text-sm text-muted">
          {titulo}
        </div>
        {paises.map(fila)}
      </div>
    );

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <MagnifyingGlass size={20} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
        <Input
          ref={entrada}
          type="text"
          role="combobox"
          aria-expanded="true"
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-activedescendant={isoActivo ? idOpcion(isoActivo) : undefined}
          aria-label={textos.phoneCountrySearch}
          placeholder={textos.phoneCountrySearch}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          enterKeyHint="go"
          value={consulta}
          onChange={(e) => {
            setConsulta(e.target.value);
            setActivo(0);
          }}
          onKeyDown={alTeclear}
          className="pl-11"
        />
      </div>

      <div
        onPointerMove={() => setPorTeclado(false)}
        className={cn('overflow-y-auto overscroll-contain', claseLista)}
      >
        {filas.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
            <p className="text-base text-foreground sm:text-sm">{textos.phoneCountryNone}</p>
            <p className="text-sm text-muted">{textos.phoneCountryNoneHint}</p>
          </div>
        ) : (
          <div id={idLista} role="listbox" aria-label={textos.phoneCountry}>
            {agrupado ? (
              <>
                {grupo('frecuentes', textos.phoneCountryFrequent, frecuentes)}
                {grupo('otros', textos.phoneCountryAll, otros)}
              </>
            ) : (
              resultados.map(fila)
            )}
          </div>
        )}
      </div>

      <p role="status" className="sr-only">
        {anuncio}
      </p>
    </div>
  );
}
