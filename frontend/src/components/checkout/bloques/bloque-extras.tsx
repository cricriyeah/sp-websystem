'use client';

import { Minus, Plus, Warning } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { BloqueDePaso } from '@/components/checkout-section-card';
import { SelectPersonalizado } from '@/components/checkout/select-personalizado';
import { CLASES_CAMPO_CON_ERROR, ErrorDeCampo } from '@/components/field-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Moneda, ServicioPersonalizacionCatalogo } from '@/lib/api';
import { aMoneda } from '@/lib/moneda';
import {
  cantidadEfectiva,
  separarPersonalizaciones,
  type SeleccionPersonalizacion,
} from '@/lib/personalizaciones';

type Props = {
  checkout: Dictionary['checkout'];
  catalogo: ServicioPersonalizacionCatalogo[];
  /** Lo elegido, por id del extra. */
  seleccionadas: Map<number, SeleccionPersonalizacion>;
  /** Código de error por id del extra. */
  errores: Record<number, string>;
  /** Con el pago en curso nada de esto se puede cambiar. */
  locked: boolean;
  people: number;
  moneda: Moneda;
  tipoCambioUsd: string | undefined;
  currency: Intl.NumberFormat;
  onAlternar: (id: number, marcado: boolean) => void;
  onRespuesta: (id: number, respuesta: string) => void;
  onCantidad: (id: number, delta: number) => void;
};

/**
 * Contenido del paso de extras («detalles»): lo obligatorio antes que lo
 * opcional. Sin estado propio: las selecciones y sus errores viven en
 * `CheckoutView` (el precio y la reserva las leen), así que plegar la
 * tarjeta no pierde nada.
 */
export function BloqueExtras({
  checkout,
  catalogo,
  seleccionadas,
  errores,
  locked,
  people,
  moneda,
  tipoCambioUsd,
  currency,
  onAlternar,
  onRespuesta,
  onCantidad,
}: Props) {
  // "2 de 5": leyenda para el extra con cantidad editable para decir la cantidad elegida.
  const deLabel = (cantidad: number, total: number) =>
    checkout.cantidadDeLabel.replace('{cantidad}', String(cantidad)).replace('{total}', String(total));

  const renderPersonalizacion = (sp: ServicioPersonalizacionCatalogo) => {
    const seleccion = seleccionadas.get(sp.id);
    const marcada = Boolean(seleccion);
    const errorCodigo = errores[sp.id] as
      | 'required'
      | 'number'
      | 'selection'
      | undefined;
    const errorId = `error-personalizacion-${sp.id}`;
    const precio = aMoneda(sp.precio, moneda, tipoCambioUsd);

    if (sp.tipo_interaccion === 'check') {
      const cantidad = cantidadEfectiva(sp, people, seleccion?.cantidad);
      return (
        <div key={sp.id}>
          <label
            htmlFor={`personalizacion-${sp.id}`}
            className="flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
          >
            <span className="flex items-start gap-3">
              <Input
                aspecto="heredado"
                id={`personalizacion-${sp.id}`}
                type="checkbox"
                checked={marcada}
                disabled={locked}
                onChange={(e) => onAlternar(sp.id, e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
              />
              <span>
                <span className="font-medium">{sp.nombre}</span>
                {sp.preseleccionado && (
                  <span className="ml-2 text-xs font-medium text-accent">
                    {checkout.recommendedBadge}
                  </span>
                )}
              </span>
            </span>
            <span className="shrink-0 text-right text-muted">
              {precio === null
                ? checkout.extrasUnavailableInCurrency
                : currency.format(Number(precio) * cantidad)}
            </span>
          </label>
          {!marcada && sp.aviso_reforzado && (
            <div className="flex items-start gap-2 border border-t-0 border-action/40 bg-action/10 px-4 py-2.5 text-xs text-foreground">
              <Warning size={14} className="mt-0.5 shrink-0 text-action" />
              <p>{checkout.amenitiesModal.reinforcedWarning}</p>
            </div>
          )}
          {marcada && sp.cantidad_editable && people > 1 && (
            <div className="flex items-center justify-between gap-3 border border-t-0 border-border bg-surface px-4 py-2.5 text-sm text-foreground">
              <span className="text-muted">{checkout.licenseQuantity.question}</span>
              <span className="flex items-center gap-2">
                <Button
                  variante="libre"
                  type="button"
                  onClick={() => onCantidad(sp.id, -1)}
                  disabled={locked || cantidad <= 1}
                  aria-label="-"
                  className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30"
                >
                  <Minus size={12} />
                </Button>
                <span>{deLabel(cantidad, people)}</span>
                <Button
                  variante="libre"
                  type="button"
                  onClick={() => onCantidad(sp.id, 1)}
                  disabled={locked || cantidad >= people}
                  aria-label="+"
                  className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30"
                >
                  <Plus size={12} />
                </Button>
              </span>
            </div>
          )}
        </div>
      );
    }

    const valor = seleccion?.respuesta ?? '';
    if (sp.tipo_interaccion === 'input_seleccion') {
      return (
        <div key={sp.id} className="flex flex-col gap-2 text-sm text-foreground">
          <SelectPersonalizado
            label={`${sp.nombre}${sp.obligatorio ? ' *' : ''}`}
            value={valor}
            disabled={locked}
            invalido={Boolean(errorCodigo)}
            sinRespuestaLabel="—"
            opciones={sp.opciones_seleccion.map((opcion) => ({ valor: opcion, etiqueta: opcion }))}
            onChange={(nuevo) => onRespuesta(sp.id, nuevo)}
          />
          <ErrorDeCampo id={errorId} mensaje={errorCodigo ? checkout.personalizacionErrors[errorCodigo] : ''} />
        </div>
      );
    }
    return (
      <label
        key={sp.id}
        htmlFor={`personalizacion-${sp.id}`}
        className="flex flex-col gap-2 text-sm text-foreground"
      >
        <span className="font-medium">
          {sp.nombre}
          {sp.obligatorio ? ' *' : ''}
        </span>
        <Input
          aspecto="heredado"
          id={`personalizacion-${sp.id}`}
          type={sp.tipo_interaccion === 'input_numero' ? 'number' : 'text'}
          step={sp.tipo_interaccion === 'input_numero' ? 'any' : undefined}
          value={valor}
          disabled={locked}
          aria-invalid={Boolean(errorCodigo)}
          aria-describedby={errorCodigo ? errorId : undefined}
          onChange={(e) => onRespuesta(sp.id, e.target.value)}
          className={`border bg-surface px-4 py-3 outline-none ${
            errorCodigo ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
          }`}
        />
        <ErrorDeCampo id={errorId} mensaje={errorCodigo ? checkout.personalizacionErrors[errorCodigo] : ''} />
      </label>
    );
  };

  const { obligatorias, opcionales } = separarPersonalizaciones(catalogo);

  return (
    <>
      {catalogo.length === 0 && (
        <p className="text-sm text-muted">{checkout.noExtrasSelected}</p>
      )}
      {obligatorias.length > 0 && (
        <BloqueDePaso titulo={checkout.extrasRequiredLabel}>
          {obligatorias.map(renderPersonalizacion)}
        </BloqueDePaso>
      )}
      {opcionales.length > 0 && (
        <BloqueDePaso titulo={checkout.extrasOptionalLabel} opcional={checkout.optionalTag}>
          {opcionales.map(renderPersonalizacion)}
        </BloqueDePaso>
      )}
    </>
  );
}
