'use client';

import { AirplaneTilt, Minus, Plus, Warning } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BloqueDePaso } from '@/components/checkout-section-card';
import { CAJA_CONTENEDOR } from '@/components/ui/caja-campo';
import { DescripcionExtra, textoDeExtra } from '@/components/checkout/descripcion-extra';
import { SelectPersonalizado } from '@/components/checkout/select-personalizado';
import { PeopleStepper } from '@/components/people-stepper';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Aeropuerto, Moneda, PaqueteServicioCatalogo } from '@/lib/api';
import { fechaDeComponente, sumarDias } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import { cantidadEfectiva, separarPersonalizaciones, type SeleccionPersonalizacion } from '@/lib/personalizaciones';
import { formatearPrecio } from '@/lib/pricing-paquete';
import type { ComponentePedido, DetalleTraslado } from '@/lib/pedido-payload';
import { TipoTrasladoCards } from '@/components/checkout/tipo-traslado-cards';
import { Despliegue } from '@/components/ui/despliegue';
import { FechaRegresoCompacta } from './fecha-paquete';

type Props = {
  lang: Locale;
  dict: Dictionary;
  componente: PaqueteServicioCatalogo;
  precioDependeDePersonas: boolean;
  esActividadPrincipal: boolean;
  personasMax: number;
  trasladoFijo: boolean;
  estado: ComponentePedido;
  moneda: Moneda;
  tipoCambio: string;
  inicio: string | null;
  noches: number | null;
  salida: string | null;
  /** Con la tarjeta completada nada de esto se puede cambiar. */
  bloqueado: boolean;
  onTope?: () => void;
  onPersonas: (personas: number) => void;
  onExtras: (seleccion: SeleccionPersonalizacion[]) => void;
  onTraslado: (cambios: Partial<DetalleTraslado>) => void;
};

/**
 * Mitad "viaje" de la tarjeta de un servicio del paquete: tipo de traslado y
 * fecha de regreso, personas y extras. Sin estado propio: todo vive en el
 * reducer del pedido (`use-pedido-estado`), así que plegar la tarjeta no
 * pierde lo elegido. Devuelve un fragmento: sus hijos son hijos directos de la
 * tarjeta, igual que cuando eran parte de `GrupoServicio`.
 */
export function GrupoViaje({
  lang, dict, componente, precioDependeDePersonas, esActividadPrincipal, personasMax, trasladoFijo, estado, moneda, tipoCambio,
  inicio, noches, salida, bloqueado,
  onTope, onPersonas, onExtras, onTraslado,
}: Props) {
  const { checkout, booking, pedido, traslados } = dict;
  const servicio = componente.servicio;
  const traslado = estado.traslado;
  const seleccionadas = new Map(estado.extras.map((extra) => [extra.id, extra]));
  const actualizarExtra = (id: number, siguiente?: SeleccionPersonalizacion) => {
    const restantes = estado.extras.filter((extra) => extra.id !== id);
    onExtras(siguiente ? [...restantes, siguiente] : restantes);
  };
  const formatoFecha = (iso: string) => new Intl.DateTimeFormat(intlLocale(lang), {
    day: 'numeric', month: 'long', year: 'numeric',
  }).format(fromLocalISODate(iso));
  const personasTexto = estado.personas === 1 ? pedido.forOne : pedido.forPeople.replace('{n}', String(estado.personas));
  const esLogistica = precioDependeDePersonas && !esActividadPrincipal &&
    (servicio.tipo_servicio === 'hospedaje' || servicio.tipo_servicio === 'transporte');
  const maxPersonasLogistica = Math.min(personasMax, componente.personas_incluidas);
  const { obligatorias, opcionales } = separarPersonalizaciones(servicio.personalizaciones);
  const renderExtra = (extra: (typeof servicio.personalizaciones)[number]) => {
    const seleccion = seleccionadas.get(extra.id);
    const marcada = Boolean(seleccion);
    const precio = aMoneda(extra.precio, moneda, tipoCambio);
    const sinPrecio = precio === null;
    const cantidad = cantidadEfectiva(extra, estado.personas, seleccion?.cantidad);
    const id = `pedido-extra-${servicio.slug}-${extra.id}`;
    const descripcionId = `${id}-descripcion`;
    const texto = textoDeExtra(extra.descripcion, lang);

    if (extra.tipo_interaccion === 'check') return (
      <div key={extra.id}>
        <label
          htmlFor={id}
          className="flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-cafe-bruma"
        >
          <span className="flex items-start gap-3">
            <Input
              aspecto="heredado"
              id={id}
              type="checkbox"
              checked={marcada}
              aria-describedby={texto ? descripcionId : undefined}
              disabled={bloqueado || (sinPrecio && !marcada)}
              onChange={(event) => actualizarExtra(extra.id, event.target.checked ? { id: extra.id, cantidad: 1 } : undefined)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
            />
            <span>
              <span className="font-medium">{extra.nombre}</span>
              {extra.preseleccionado && (
                <span className="ml-2 text-sm font-medium text-accent">{checkout.recommendedBadge}</span>
              )}
              <DescripcionExtra id={descripcionId} texto={texto} />
            </span>
          </span>
          <span className="shrink-0 text-right text-muted">
            {sinPrecio ? checkout.extrasUnavailableInCurrency : `+${formatearPrecio(precio * cantidad, moneda)}`}
          </span>
        </label>
        <Despliegue abierto={!marcada && Boolean(extra.aviso_reforzado)}>
          <div className="flex items-start gap-2 border border-t-0 border-aviso/40 bg-aviso-fondo px-4 py-2.5 text-sm text-foreground">
            <Warning size={14} className="mt-0.5 shrink-0 text-aviso" />
            <p>{checkout.amenitiesModal.reinforcedWarning}</p>
          </div>
        </Despliegue>
        <Despliegue abierto={marcada && Boolean(extra.cantidad_editable) && estado.personas > 1}>
          <div className="flex items-center justify-between gap-3 border border-t-0 border-border bg-cafe-bruma px-4 py-2.5 text-sm text-foreground">
            <span className="text-muted">{checkout.licenseQuantity.question}</span>
            <span className="flex items-center gap-2">
              <Button variante="libre" type="button" aria-label="-" disabled={cantidad <= 1 || bloqueado}
                onClick={() => actualizarExtra(extra.id, { id: extra.id, cantidad: cantidad - 1 })}
                className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30">
                <Minus size={12} />
              </Button>
              <span>{checkout.cantidadDeLabel.replace('{cantidad}', String(cantidad)).replace('{total}', String(estado.personas))}</span>
              <Button variante="libre" type="button" aria-label="+" disabled={cantidad >= estado.personas || bloqueado}
                onClick={() => actualizarExtra(extra.id, { id: extra.id, cantidad: cantidad + 1 })}
                className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30">
                <Plus size={12} />
              </Button>
            </span>
          </div>
        </Despliegue>
      </div>
    );

    if (extra.tipo_interaccion === 'input_seleccion') {
      return (
        <div key={extra.id} className="text-sm text-foreground">
          <SelectPersonalizado
            label={`${extra.nombre}${extra.obligatorio ? ' *' : ''}`}
            value={seleccion?.respuesta ?? ''}
            disabled={bloqueado}
            sinRespuestaLabel="–"
            opciones={extra.opciones_seleccion.map((opcion) => ({ valor: opcion, etiqueta: opcion }))}
            onChange={(valor) => actualizarExtra(extra.id, valor ? { id: extra.id, respuesta: valor } : undefined)}
          />
          <DescripcionExtra id={descripcionId} texto={texto} />
        </div>
      );
    }

    return (
      <label key={extra.id} htmlFor={id} className="flex flex-col gap-2 text-sm text-foreground">
        <span className="font-medium">
          {extra.nombre}{extra.obligatorio ? ' *' : ''}
          <DescripcionExtra id={descripcionId} texto={texto} />
        </span>
        <Input aspecto="heredado" id={id} aria-describedby={texto ? descripcionId : undefined} type={extra.tipo_interaccion === 'input_numero' ? 'number' : 'text'}
          step={extra.tipo_interaccion === 'input_numero' ? 'any' : undefined}
          value={seleccion?.respuesta ?? ''} disabled={bloqueado}
          onChange={(event) => actualizarExtra(extra.id, event.target.value ? { id: extra.id, respuesta: event.target.value } : undefined)}
          className="border border-border bg-superficie px-4 py-3 outline-none focus:border-accent" />
      </label>
    );
  };

  return (
    <>
  {traslado && trasladoFijo && (
    <BloqueDePaso>
      <div>
        <p className="text-sm font-medium text-foreground">{pedido.fixedTransfer}</p>
        {inicio && salida && (
          <p className="mt-1 text-sm text-muted">
            {pedido.fixedTransferDates
              .replace('{llegada}', formatoFecha(fechaDeComponente(inicio, componente.dia_estancia)))
              .replace('{salida}', formatoFecha(salida))}
          </p>
        )}
      </div>
      <div className="text-sm text-foreground">
        <SelectPersonalizado
          label={pedido.airportLabel}
          placeholder={pedido.airportLabel}
          value={traslado.aeropuerto}
          disabled={bloqueado}
          icon={<AirplaneTilt size={20} className="shrink-0 text-muted" />}
          opciones={(['lap', 'sjd'] as Aeropuerto[]).map((codigo) => ({ valor: codigo, etiqueta: pedido.airports[codigo] }))}
          onChange={(valor) => onTraslado({ aeropuerto: valor as Aeropuerto | '' })}
        />
      </div>
    </BloqueDePaso>
  )}

  {traslado && !trasladoFijo && (
    // Un solo hijo de la tarjeta: la separación entre preguntas (`pt-5`) vive
    // dentro de cada bloque. Así, al aparecer el regreso, no brinca el hueco
    // que el cuerpo de la tarjeta pondría entre hijos antes de que crezca.
    <div>
      <BloqueDePaso titulo={traslados.step1Title}>
        <TipoTrasladoCards
          tipos={['redondo_aeropuerto', 'redondo_actividad', 'recepcion_aeropuerto']}
          valor={traslado.tipo}
          textos={traslados.types}
          etiqueta={traslados.step1Title}
          onChange={(tipo) => onTraslado({ tipo })}
        />
      </BloqueDePaso>

      {/* El regreso depende del tipo: aparece pegado a las tarjetas que lo
          provocan y sin prellenar (sin respuesta se ve la pregunta). */}
      {inicio && (
        <Despliegue abierto={traslado.tipo === 'redondo_aeropuerto' && noches === null}>
          <div className="pt-5">
            <FechaRegresoCompacta lang={lang} label={traslados.fields.fechaRegreso} value={traslado.fechaRegreso}
              onChange={(fechaRegreso) => onTraslado({ fechaRegreso })}
              minDate={sumarDias(fechaDeComponente(inicio, componente.dia_estancia), 1)}
              chooseLabel={pedido.chooseReturnDate}
              changeButtonLabel={checkout.changeStep} doneButtonLabel={checkout.doneEditing}
              viewMonthLabel={pedido.viewMonth} hideMonthLabel={pedido.hideMonth}
              previousWeekLabel={pedido.previousWeek} nextWeekLabel={pedido.nextWeek}
              previousMonthLabel={booking.prevMonth} nextMonthLabel={booking.nextMonth}
              personas={estado.personas} fullLabel={checkout.dayFull} />
          </div>
        </Despliegue>
      )}

    </div>
  )}

  {/* Lo prellenado va al final y callado: llega resuelto del paso anterior, así
      que no merece ser lo primero que el cliente lee en la tarjeta. */}
  {esLogistica ? (
    <div className={CAJA_CONTENEDOR}>
      <PeopleStepper
        compacto
        label={servicio.tipo_servicio === 'hospedaje' ? pedido.stayPeopleQuestion : pedido.transferPeopleQuestion}
        maxNotice={pedido.logisticsMaxNotice.replace('{max}', String(maxPersonasLogistica))}
        value={estado.personas}
        onChange={onPersonas}
        maxPeople={maxPersonasLogistica}
        minPeople={1}
        disabled={bloqueado}
        onMaxAttempt={onTope}
      />
    </div>
  ) : precioDependeDePersonas ? (
    <p className="text-sm text-muted">{personasTexto}</p>
  ) : (
    <div>
      <div className={CAJA_CONTENEDOR}>
        <PeopleStepper
          compacto
          label={checkout.peopleLabel}
          maxNotice={pedido.maxPeoplePackage.replace('{max}', String(componente.personas_incluidas))}
          value={estado.personas}
          onChange={onPersonas}
          maxPeople={componente.personas_incluidas}
          minPeople={1}
          disabled={bloqueado}
          onMaxAttempt={onTope}
        />
      </div>
      <p className="mt-2 text-sm text-muted">
        {pedido.peopleIncluded.replace('{n}', String(componente.personas_incluidas))}
      </p>
    </div>
  )}

  {obligatorias.length > 0 && (
    <BloqueDePaso titulo={checkout.extrasRequiredLabel}>
      {obligatorias.map(renderExtra)}
    </BloqueDePaso>
  )}
  {opcionales.length > 0 && (
    <BloqueDePaso titulo={pedido.extrasTitle} opcional={checkout.optionalTag}>
      {opcionales.map(renderExtra)}
    </BloqueDePaso>
  )}
    </>
  );
}
