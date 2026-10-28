'use client';

import { useEffect, useId, useMemo, useState, type Ref } from 'react';
import { CaretDown } from '@phosphor-icons/react';
import { FieldPopover } from '@/components/field-popover';
import { SelectorPais, type TextosSelectorPais } from '@/components/checkout/selector-pais';
import { useMovil } from '@/components/reserva/use-movil';
import { Bandera } from '@/components/ui/bandera';
import { Button } from '@/components/ui/button';
import { CAJA_CONTENEDOR, CAJA_CONTENEDOR_ERROR } from '@/components/ui/caja-campo';
import { cn } from '@/components/ui/cn';
import { Despliegue } from '@/components/ui/despliegue';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import { Input } from '@/components/ui/input';
import { Sheet } from '@/components/ui/sheet';
import { listarPaises } from '@/lib/paises-telefono';
import { evaluar, formatearTelefono, PAIS_POR_DEFECTO } from '@/lib/telefono';
import { alCambiarPais, alEscribir, alSalir, estadoInicial, type EstadoTelefono } from '@/lib/telefono-campo';

/** Textos del campo (claves `checkout.*` del diccionario, mismo nombre; `cerrar` es `checkout.barra.cerrar`). */
export type TextosTelefono = TextosSelectorPais & {
  /** Lleva `{pais}` y `{codigo}`. */
  phoneCountryChanged: string;
  phonePlaceholderOther: string;
  cerrar: string;
};

type Props = {
  /** Prefijo de los ids (`checkout`, `traslado`): el error es `<prefijo>-error-phone`, igual que los otros campos. */
  idPrefijo: string;
  /** Valor compacto del formulario: '' o `+<código><lo tecleado>`. Un valor viejo se restaura sin borrarlo. */
  valor: string;
  onCambio: (valor: string) => void;
  etiqueta: string;
  /** Ejemplo del número (`Ej. 612 123 4567`); solo se muestra con México elegido. */
  ejemplo?: string;
  /**
   * Mensaje de error ya elegido por quien valida (`invalidPhone` o `phoneUnknownCode`). Puede traer
   * `{pais}` y `{codigo}`: el campo los llena con el país elegido, así quien valida no los reemplaza.
   */
  error?: string;
  lang: string;
  textos: TextosTelefono;
  refInput?: Ref<HTMLInputElement>;
  disabled?: boolean;
  /** Clases de la celda en la rejilla de contacto (p. ej. `sm:col-span-1`). */
  className?: string;
};

// Mismo relleno y separación en el popover y en la hoja; el ancho es FIJO para que cambiar de país no
// mueva el número. El caret gira al abrir (motivo: dice que el panel está abierto).
const CLASE_BOTON = 'gap-2 px-3 tabular-nums';
const CLASE_CARET_POPOVER =
  '[&>svg:last-child]:transition-transform [&>svg:last-child]:duration-[var(--duracion-corta)] ' +
  'motion-reduce:[&>svg:last-child]:transition-none [&[aria-expanded=true]>svg:last-child]:rotate-180';

/**
 * Teléfono con selector de país: dos cajas hermanas (país | número) con UNA etiqueta arriba y UN
 * mensaje debajo (`div role="group"`; la etiqueta apunta al número, el botón de país no va dentro de
 * un `<label>`). México por defecto y editable. Escribir, pegar o autocompletar con `+` o `00` mueve
 * el selector solo; cambiar de país no toca lo escrito. No se formatea ni se valida mientras se
 * teclea: al salir del campo se canoniza, y el error lo decide quien valida (`error`). Cuando el
 * número ya es posible, una línea dice país y número formateado (defensa contra dejar México y
 * teclear el número de otro país). El estado del país vive aquí; lo de lógica pura, en
 * `lib/telefono-campo.ts`.
 */
export function TelefonoCampo({ idPrefijo, valor, onCambio, etiqueta, ejemplo, error, lang, textos, refInput, disabled = false, className }: Props) {
  const base = useId();
  const idEtiqueta = `${base}-etiqueta`;
  const idEntrada = `${idPrefijo}-phone`;
  const idError = `${idPrefijo}-error-phone`;
  const idConfirmacion = `${base}-confirmacion`;
  const movil = useMovil();

  const [estado, setEstado] = useState<EstadoTelefono>(() => estadoInicial(valor));
  // Si el valor de fuera cambia por otra razón que lo que este campo emitió (restauración tardía,
  // reinicio), el campo se rehace desde él. Si es el eco de lo emitido, no se toca nada.
  const [externo, setExterno] = useState(valor);
  if (valor !== externo) {
    setExterno(valor);
    if (valor !== estado.valor) setEstado(estadoInicial(valor));
  }

  const paises = useMemo(() => listarPaises(lang), [lang]);
  const datosDe = (iso: string) => {
    const pais = paises.find((p) => p.iso === iso);
    return { nombre: pais?.nombre ?? iso, codigo: pais?.codigo ?? '' };
  };
  const { nombre, codigo } = datosDe(estado.iso);
  const rotulo = `${textos.phoneCountry}: ${nombre} +${codigo}`;

  const [hojaAbierta, setHojaAbierta] = useState(false);
  if (!movil && hojaAbierta) setHojaAbierta(false);

  const [anuncio, setAnuncio] = useState('');
  useEffect(() => {
    if (!anuncio) return;
    const olvidar = window.setTimeout(() => setAnuncio(''), 4000);
    return () => window.clearTimeout(olvidar);
  }, [anuncio]);
  const anunciarPais = (iso: string) => {
    const datos = datosDe(iso);
    setAnuncio(textos.phoneCountryChanged.replace('{pais}', datos.nombre).replace('{codigo}', '+' + datos.codigo));
  };

  // Teclado en pantalla: la hoja se levanta sobre él. Sin visualViewport vale 0 y la lista se desplaza.
  useEffect(() => {
    if (!hojaAbierta) return;
    const vista = window.visualViewport;
    if (!vista) return;
    const raiz = document.documentElement;
    const medir = () => raiz.style.setProperty('--teclado', `${Math.max(0, Math.round(window.innerHeight - vista.height - vista.offsetTop))}px`);
    medir();
    vista.addEventListener('resize', medir);
    vista.addEventListener('scroll', medir);
    return () => {
      vista.removeEventListener('resize', medir);
      vista.removeEventListener('scroll', medir);
      raiz.style.removeProperty('--teclado');
    };
  }, [hojaAbierta]);

  const emitir = (nuevo: EstadoTelefono) => {
    setEstado(nuevo);
    if (nuevo.valor !== estado.valor) onCambio(nuevo.valor);
  };

  const elegirPais = (iso: string, cerrar: () => void) => {
    if (iso !== estado.iso) anunciarPais(iso);
    emitir(alCambiarPais(estado.texto, iso));
    cerrar();
    // En escritorio lo natural es seguir con el número; en la hoja el foco vuelve al botón de país.
    if (!movil) document.getElementById(idEntrada)?.focus();
  };

  const alEscribirNumero = (crudo: string) => {
    const nuevo = alEscribir(estado.iso, crudo);
    if (nuevo.iso !== estado.iso) anunciarPais(nuevo.iso);
    emitir(nuevo);
  };

  const mensajeError = error ? error.replace('{pais}', nombre).replace('{codigo}', '+' + codigo) : undefined;

  const formato = !mensajeError && evaluar(estado.valor) === 'ok' ? formatearTelefono(estado.valor, estado.iso) : null;
  // Conserva el último texto mientras la línea se pliega.
  const [ultimaConfirmacion, setUltimaConfirmacion] = useState('');
  const confirmacion = formato ? `${nombre} · ${formato.texto}` : null;
  if (confirmacion && confirmacion !== ultimaConfirmacion) setUltimaConfirmacion(confirmacion);

  const selector = (cerrar: () => void, tactil: boolean) => (
    <SelectorPais
      lang={lang}
      seleccion={estado.iso}
      onElegir={(iso) => elegirPais(iso, cerrar)}
      textos={textos}
      enfocar={!tactil}
      tactil={tactil}
      claseLista={tactil ? 'h-[max(8rem,calc(85dvh_-_8.5rem_-_var(--teclado,0px)))]' : 'h-[min(22rem,calc(100dvh_-_14rem))]'}
      onTab={tactil ? undefined : cerrar}
    />
  );

  return (
    <div role="group" aria-labelledby={idEtiqueta} className={cn('flex flex-col gap-1.5 text-base sm:text-sm', className)}>
      <label id={idEtiqueta} htmlFor={idEntrada} className="text-muted">
        {etiqueta}
      </label>

      <div className="flex gap-2">
        <div
          inert={disabled}
          className={cn(
            mensajeError ? CAJA_CONTENEDOR_ERROR : CAJA_CONTENEDOR,
            'flex w-[7.5rem] shrink-0',
            disabled && 'bg-cafe-bruma text-apagado',
          )}
        >
          {movil ? (
            <Button
              variante="libre"
              aria-haspopup="dialog"
              aria-expanded={hojaAbierta}
              aria-label={rotulo}
              onClick={() => setHojaAbierta(true)}
              className={cn('group flex flex-1 items-center text-left text-base transition-colors hover:bg-cafe-bruma', CLASE_BOTON)}
            >
              <Bandera iso={estado.iso} tam="m" prioritaria />
              <span className="min-w-0 flex-1 truncate text-foreground">+{codigo}</span>
              <CaretDown
                size={16}
                aria-hidden="true"
                className="shrink-0 text-muted transition-transform duration-[var(--duracion-corta)] group-aria-expanded:rotate-180 motion-reduce:transition-none"
              />
            </Button>
          ) : (
            <FieldPopover
              label={textos.phoneCountry}
              etiquetaDisparador={rotulo}
              claseDisparador={cn(CLASE_BOTON, CLASE_CARET_POPOVER)}
              value={`+${codigo}`}
              icon={<Bandera iso={estado.iso} tam="m" prioritaria />}
              compacto
            >
              {(cerrar) => <div className="w-full sm:w-80">{selector(cerrar, false)}</div>}
            </FieldPopover>
          )}
        </div>

        <Input
          id={idEntrada}
          ref={refInput}
          type="tel"
          inputMode="tel"
          enterKeyHint="next"
          autoComplete="tel"
          dir="ltr"
          required
          disabled={disabled}
          value={estado.texto}
          placeholder={estado.iso === PAIS_POR_DEFECTO ? ejemplo : textos.phonePlaceholderOther}
          onChange={(e) => alEscribirNumero(e.target.value)}
          onBlur={() => emitir(alSalir(estado))}
          aria-invalid={mensajeError ? true : undefined}
          aria-describedby={mensajeError ? idError : formato ? idConfirmacion : undefined}
          className="min-w-0 flex-1"
        />
      </div>

      <ErrorDeCampo id={idError} mensaje={mensajeError} />

      <Despliegue abierto={Boolean(confirmacion)}>
        <p id={idConfirmacion} className="text-sm tabular-nums text-muted">
          {ultimaConfirmacion}
        </p>
      </Despliegue>

      <p role="status" className="sr-only">
        {anuncio}
      </p>

      {movil && (
        <Sheet abierto={hojaAbierta} onCerrar={() => setHojaAbierta(false)} titulo={textos.phoneCountry} etiquetaCerrar={textos.cerrar} className="bottom-[var(--teclado,0px)]">
          {selector(() => setHojaAbierta(false), true)}
        </Sheet>
      )}
    </div>
  );
}
