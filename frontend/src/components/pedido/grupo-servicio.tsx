'use client';

import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import type { Moneda, PaqueteServicioCatalogo } from '@/lib/api';
import type { SeleccionPersonalizacion } from '@/lib/personalizaciones';
import type { ComponentePedido, DetalleTraslado } from '@/lib/pedido-payload';
import { GrupoViaje } from './grupo-viaje';

type Props = {
  lang: Locale;
  dict: Dictionary;
  componente: PaqueteServicioCatalogo;
  precioDependeDePersonas: boolean;
  esActividadPrincipal: boolean;
  personasMax: number;
  trasladoFijo: boolean;
  estado: ComponentePedido;
  conEncabezadoEmpresa: boolean;
  nombreEmpresa: string;
  /** Logo de la empresa (de `content/empresas`); sin él, el sello pinta el monograma. */
  moneda: Moneda;
  tipoCambio: string;
  inicio: string | null;
  noches: number | null;
  salida: string | null;
  estadoTarjeta: 'activo' | 'editando' | 'completado' | 'suspendido';
  /** Error de validación de ESTA tarjeta: se muestra pegado a su CTA, no entre otras tarjetas. */
  error?: string;
  onAccion: () => void;
  onCompletar: () => void;
  onTope?: () => void;
  onPersonas: (personas: number) => void;
  onExtras: (seleccion: SeleccionPersonalizacion[]) => void;
  onTraslado: (cambios: Partial<DetalleTraslado>) => void;
};

export function GrupoServicio({
  lang, dict, componente, precioDependeDePersonas, esActividadPrincipal, personasMax, trasladoFijo, estado, conEncabezadoEmpresa, nombreEmpresa, moneda, tipoCambio,
  inicio, noches, salida, estadoTarjeta,
  onAccion, onCompletar, onTope, onPersonas, onExtras, onTraslado, error,
}: Props) {
  const { checkout } = dict;
  const servicio = componente.servicio;
  const bloqueado = estadoTarjeta === 'completado';

  return (
    <CheckoutSectionCard
      title={servicio.nombre}
      etiqueta={conEncabezadoEmpresa ? nombreEmpresa : undefined}
      estado={estadoTarjeta}
      actionLabel={estadoTarjeta === 'completado' ? checkout.changeStep : estadoTarjeta === 'editando' ? checkout.doneEditing : undefined}
      onAction={estadoTarjeta === 'activo' ? undefined : onAccion}
      pie={estadoTarjeta === 'activo' ? (
        <BotonPaso onClick={onCompletar}>{checkout.confirmStep}</BotonPaso>
      ) : undefined}
    >
      <GrupoViaje
        lang={lang}
        dict={dict}
        componente={componente}
        precioDependeDePersonas={precioDependeDePersonas}
        esActividadPrincipal={esActividadPrincipal}
        personasMax={personasMax}
        trasladoFijo={trasladoFijo}
        estado={estado}
        moneda={moneda}
        tipoCambio={tipoCambio}
        inicio={inicio}
        noches={noches}
        salida={salida}
        bloqueado={bloqueado}
        onTope={onTope}
        onPersonas={onPersonas}
        onExtras={onExtras}
        onTraslado={onTraslado}
      />

      <ErrorDeCampo id="pedido-detalles-error" mensaje={error ?? ''} />
    </CheckoutSectionCard>
  );
}
