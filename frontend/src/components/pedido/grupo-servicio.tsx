'use client';

import { Buildings, MapPin, Minus, Plus, Warning } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutSectionCard } from '@/components/checkout-section-card';
import { FieldPopover } from '@/components/field-popover';
import { PeopleStepper } from '@/components/people-stepper';
import type { Aeropuerto, Moneda, PaqueteServicioCatalogo, PuntoEncuentro, TipoTraslado, Zona } from '@/lib/api';
import { fechaDeComponente, sumarDias } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import { cantidadEfectiva, type SeleccionPersonalizacion } from '@/lib/personalizaciones';
import { formatearPrecio } from '@/lib/pricing-paquete';
import type { ComponentePedido, DetalleTraslado } from '@/lib/pedido-payload';
import { FechaPaquete } from './fecha-paquete';

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
  moneda: Moneda;
  tipoCambio: string;
  inicio: string | null;
  noches: number | null;
  salida: string | null;
  minDate: string;
  puntos: PuntoEncuentro[];
  mostrarInicio: boolean;
  estadoTarjeta: 'activo' | 'editando' | 'completado';
  onAccion: () => void;
  onCompletar: () => void;
  onInicio: (fecha: string) => void;
  onPersonas: (personas: number) => void;
  onExtras: (seleccion: SeleccionPersonalizacion[]) => void;
  onTraslado: (cambios: Partial<DetalleTraslado>) => void;
};

export function GrupoServicio({
  lang, dict, componente, precioDependeDePersonas, esActividadPrincipal, personasMax, trasladoFijo, estado, conEncabezadoEmpresa, nombreEmpresa, moneda, tipoCambio,
  inicio, noches, salida, minDate, puntos, mostrarInicio, estadoTarjeta,
  onAccion, onCompletar, onInicio, onPersonas, onExtras, onTraslado,
}: Props) {
  const { checkout, booking, pedido, traslados } = dict;
  const servicio = componente.servicio;
  const traslado = estado.traslado;
  const bloqueado = estadoTarjeta === 'completado';
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
  const resumen = [
    conEncabezadoEmpresa ? pedido.groupOf.replace('{empresa}', nombreEmpresa) : null,
    precioDependeDePersonas ? personasTexto : `${estado.personas} ${estado.personas === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`,
    mostrarInicio && inicio ? formatoFecha(inicio) : null,
  ].filter(Boolean).join(' · ');

  return (
    <CheckoutSectionCard
      title={servicio.nombre}
      estado={estadoTarjeta}
      resumen={resumen}
      actionLabel={estadoTarjeta === 'completado' ? checkout.changeStep : estadoTarjeta === 'editando' ? checkout.doneEditing : undefined}
      onAction={estadoTarjeta === 'activo' ? undefined : onAccion}
    >
      {conEncabezadoEmpresa && (
        <p className="mb-4 text-xs text-muted">{pedido.groupOf.replace('{empresa}', nombreEmpresa)}</p>
      )}

      {mostrarInicio && (
        <div className="mb-4">
          <FechaPaquete
            lang={lang}
            label={pedido.startLabel}
            value={inicio}
            onChange={onInicio}
            minDate={minDate}
            chooseLabel={pedido.chooseStart}
            viewMonthLabel={pedido.viewMonth}
            hideMonthLabel={pedido.hideMonth}
            previousWeekLabel={pedido.previousWeek}
            nextWeekLabel={pedido.nextWeek}
            previousMonthLabel={booking.prevMonth}
            nextMonthLabel={booking.nextMonth}
            personas={estado.personas}
            fullLabel={checkout.dayFull}
          />
          {noches !== null && salida && (
            <p className="mt-2 text-xs text-muted">
              {pedido.nightsNote.replace('{n}', String(noches)).replace('{fecha}', formatoFecha(salida))}
            </p>
          )}
        </div>
      )}

      {esLogistica ? (
        <div className="border-t border-border pt-4">
          <PeopleStepper
            label={servicio.tipo_servicio === 'hospedaje' ? pedido.stayPeopleQuestion : pedido.transferPeopleQuestion}
            maxNotice={pedido.logisticsMaxNotice.replace('{max}', String(maxPersonasLogistica))}
            value={estado.personas}
            onChange={onPersonas}
            maxPeople={maxPersonasLogistica}
            minPeople={1}
            disabled={bloqueado}
          />
        </div>
      ) : precioDependeDePersonas ? (
        <p className="border-t border-border pt-4 text-sm text-muted">{personasTexto}</p>
      ) : (
        <div className="border-t border-border pt-4">
          <PeopleStepper
            label={checkout.peopleLabel}
            maxNotice={booking.maxPeopleNotice}
            value={estado.personas}
            onChange={onPersonas}
            maxPeople={componente.personas_incluidas}
            minPeople={1}
            disabled={bloqueado}
          />
          <p className="px-6 text-xs text-muted">
            {pedido.peopleIncluded.replace('{n}', String(componente.personas_incluidas))}
          </p>
        </div>
      )}

      {servicio.personalizaciones.length > 0 && (
        <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5">
          <p className="text-sm font-medium text-foreground">{pedido.extrasTitle}</p>
          {servicio.personalizaciones.map((extra) => {
            const seleccion = seleccionadas.get(extra.id);
            const marcada = Boolean(seleccion);
            const precio = aMoneda(extra.precio, moneda, tipoCambio);
            const sinPrecio = precio === null;
            const cantidad = cantidadEfectiva(extra, estado.personas, seleccion?.cantidad);
            const id = `pedido-extra-${servicio.slug}-${extra.id}`;

            if (extra.tipo_interaccion === 'check') return (
              <div key={extra.id}>
                <label
                  htmlFor={id}
                  className="flex items-start justify-between gap-3 border border-border px-4 py-3 text-sm text-foreground transition-colors has-[:checked]:border-accent has-[:checked]:bg-surface"
                >
                  <span className="flex items-start gap-3">
                    <input
                      id={id}
                      type="checkbox"
                      checked={marcada}
                      disabled={bloqueado || (sinPrecio && !marcada)}
                      onChange={(event) => actualizarExtra(extra.id, event.target.checked ? { id: extra.id, cantidad: 1 } : undefined)}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                    />
                    <span>
                      <span className="font-medium">{extra.nombre}</span>
                      {extra.preseleccionado && (
                        <span className="ml-2 text-xs font-medium text-accent">{checkout.recommendedBadge}</span>
                      )}
                    </span>
                  </span>
                  <span className="shrink-0 text-right text-muted">
                    {sinPrecio ? checkout.extrasUnavailableInCurrency : `+${formatearPrecio(precio * cantidad, moneda)}`}
                  </span>
                </label>
                {!marcada && extra.aviso_reforzado && (
                  <div className="flex items-start gap-2 border border-t-0 border-action/40 bg-action/10 px-4 py-2.5 text-xs text-foreground">
                    <Warning size={14} className="mt-0.5 shrink-0 text-action" />
                    <p>{checkout.amenitiesModal.reinforcedWarning}</p>
                  </div>
                )}
                {marcada && extra.cantidad_editable && estado.personas > 1 && (
                  <div className="flex items-center justify-between gap-3 border border-t-0 border-border bg-surface px-4 py-2.5 text-sm text-foreground">
                    <span className="text-muted">{checkout.licenseQuantity.question}</span>
                    <span className="flex items-center gap-2">
                      <button type="button" aria-label="-" disabled={cantidad <= 1 || bloqueado}
                        onClick={() => actualizarExtra(extra.id, { id: extra.id, cantidad: cantidad - 1 })}
                        className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30">
                        <Minus size={12} />
                      </button>
                      <span>{checkout.cantidadDeLabel.replace('{cantidad}', String(cantidad)).replace('{total}', String(estado.personas))}</span>
                      <button type="button" aria-label="+" disabled={cantidad >= estado.personas || bloqueado}
                        onClick={() => actualizarExtra(extra.id, { id: extra.id, cantidad: cantidad + 1 })}
                        className="flex h-6 w-6 items-center justify-center rounded-full text-muted disabled:opacity-30">
                        <Plus size={12} />
                      </button>
                    </span>
                  </div>
                )}
              </div>
            );

            return (
              <label key={extra.id} htmlFor={id} className="flex flex-col gap-2 text-sm text-foreground">
                <span className="font-medium">{extra.nombre}{extra.obligatorio ? ' *' : ''}</span>
                {extra.tipo_interaccion === 'input_seleccion' ? (
                  <select id={id} value={seleccion?.respuesta ?? ''} disabled={bloqueado}
                    onChange={(event) => actualizarExtra(extra.id, event.target.value ? { id: extra.id, respuesta: event.target.value } : undefined)}
                    className="border border-border bg-surface px-4 py-3 outline-none focus:border-accent">
                    <option value="">—</option>
                    {extra.opciones_seleccion.map((opcion) => <option key={opcion} value={opcion}>{opcion}</option>)}
                  </select>
                ) : (
                  <input id={id} type={extra.tipo_interaccion === 'input_numero' ? 'number' : 'text'}
                    step={extra.tipo_interaccion === 'input_numero' ? 'any' : undefined}
                    value={seleccion?.respuesta ?? ''} disabled={bloqueado}
                    onChange={(event) => actualizarExtra(extra.id, event.target.value ? { id: extra.id, respuesta: event.target.value } : undefined)}
                    className="border border-border bg-surface px-4 py-3 outline-none focus:border-accent" />
                )}
              </label>
            );
          })}
        </div>
      )}

      {traslado && trasladoFijo && (
        <div className="mt-5 flex flex-col gap-4 border-t border-border pt-5">
          <div>
            <p className="text-sm font-medium text-foreground">{pedido.fixedTransfer}</p>
            {inicio && salida && (
              <p className="mt-1 text-xs text-muted">
                {pedido.fixedTransferDates
                  .replace('{llegada}', formatoFecha(fechaDeComponente(inicio, componente.dia_estancia)))
                  .replace('{salida}', formatoFecha(salida))}
              </p>
            )}
          </div>
          <label className="flex flex-col gap-1.5 text-sm text-foreground">
            <span className="text-muted">{pedido.airportLabel}</span>
            <select
              value={traslado.aeropuerto}
              disabled={bloqueado}
              onChange={(event) => onTraslado({ aeropuerto: event.target.value as Aeropuerto | '' })}
              className="border border-border bg-surface px-4 py-3 outline-none focus:border-accent"
            >
              <option value="">{pedido.airportPlaceholder}</option>
              {(['lap', 'sjd'] as Aeropuerto[]).map((codigo) => (
                <option key={codigo} value={codigo}>{pedido.airports[codigo]}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      {traslado && !trasladoFijo && (
        <div className="mt-5 flex flex-col gap-4 border-t border-border pt-5">
          <fieldset className="grid gap-3 sm:grid-cols-3">
            <legend className="sr-only">{traslados.step1Title}</legend>
            {(['redondo_aeropuerto', 'redondo_actividad', 'recepcion_aeropuerto'] as TipoTraslado[]).map((tipo) => (
              <label key={tipo} className={`cursor-pointer rounded-lg border p-3 text-sm transition-colors ${
                traslado.tipo === tipo ? 'border-accent bg-surface font-medium text-foreground ring-1 ring-accent' : 'border-border text-muted hover:border-border-strong'
              }`}>
                <input type="radio" name={`tipo-traslado-${servicio.slug}`} checked={traslado.tipo === tipo}
                  onChange={() => onTraslado({ tipo })} className="sr-only" />
                {traslados.types[tipo].title}
              </label>
            ))}
          </fieldset>

          {traslado.modo === 'catalogo' ? (
            <FieldPopover
              label={traslados.fields.puntoEncuentro}
              value={puntos.find((p) => p.id === traslado.puntoEncuentroId)?.nombre ?? ''}
              vacio={traslado.puntoEncuentroId === null}
              placeholder={traslados.fields.puntoEncuentroPlaceholder}
              icon={<Buildings size={20} className="shrink-0 text-muted" />}
            >
              {(cerrar) => (
                <div className="max-h-72 w-full overflow-y-auto sm:w-80">
                  {puntos.map((punto) => (
                    <button key={punto.id} type="button"
                      onClick={() => { onTraslado({ puntoEncuentroId: punto.id }); cerrar(); }}
                      className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                        punto.id === traslado.puntoEncuentroId ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground hover:bg-background'
                      }`}>
                      <span className="truncate pr-2">{punto.nombre}</span>
                    </button>
                  ))}
                </div>
              )}
            </FieldPopover>
          ) : (
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1.5 text-sm">
                <span className="text-muted">{traslados.fields.otraDireccion}</span>
                <span className="relative">
                  <MapPin size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                  <input type="text" value={traslado.direccion}
                    onChange={(event) => onTraslado({ direccion: event.target.value })}
                    placeholder={traslados.fields.direccionPlaceholder}
                    className="w-full border border-border bg-surface py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent" />
                </span>
              </label>
              {traslado.tipo === 'redondo_actividad' && (
                <fieldset className="grid grid-cols-2 gap-3">
                  <legend className="sr-only">{traslados.fields.zona}</legend>
                  {(['centro', 'periferia'] as Zona[]).map((zona) => (
                    <label key={zona} className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm ${
                      traslado.zonaLibre === zona ? 'border-accent bg-surface font-medium' : 'border-border text-muted'
                    }`}>
                      <input type="radio" name={`zona-${servicio.slug}`} checked={traslado.zonaLibre === zona}
                        onChange={() => onTraslado({ zonaLibre: zona })} className="h-4 w-4 accent-accent" />
                      {zona === 'centro' ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
                    </label>
                  ))}
                </fieldset>
              )}
            </div>
          )}

          {traslado.tipo === 'redondo_actividad' && traslado.modo === 'catalogo' && traslado.puntoEncuentroId !== null && (
            <p className="text-xs text-muted">
              {traslados.fields.zona}: {puntos.find((p) => p.id === traslado.puntoEncuentroId)?.zona === 'centro'
                ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
            </p>
          )}

          <button type="button" onClick={() => onTraslado({ modo: traslado.modo === 'catalogo' ? 'personalizada' : 'catalogo' })}
            className="self-start text-xs font-medium text-accent underline underline-offset-2">
            {traslado.modo === 'catalogo' ? traslados.fields.otraDireccion : traslados.fields.puntoEncuentro}
          </button>

          {traslado.tipo === 'redondo_aeropuerto' && noches === null && inicio && (
            <FechaPaquete lang={lang} label={traslados.fields.fechaRegreso} value={traslado.fechaRegreso}
              onChange={(fechaRegreso) => onTraslado({ fechaRegreso })}
              minDate={sumarDias(fechaDeComponente(inicio, componente.dia_estancia), 1)}
              chooseLabel={pedido.chooseReturnDate}
              viewMonthLabel={pedido.viewMonth} hideMonthLabel={pedido.hideMonth}
              previousWeekLabel={pedido.previousWeek} nextWeekLabel={pedido.nextWeek}
              previousMonthLabel={booking.prevMonth} nextMonthLabel={booking.nextMonth}
              personas={estado.personas} fullLabel={checkout.dayFull} />
          )}
        </div>
      )}

      {estadoTarjeta === 'activo' && (
        <div className="mt-6 flex justify-end border-t border-border pt-5">
          <button type="button" onClick={onCompletar}
            className="rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98]">
            {checkout.confirmStep}
          </button>
        </div>
      )}
    </CheckoutSectionCard>
  );
}
