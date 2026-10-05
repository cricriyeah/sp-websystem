'use client';

import { AirplaneTilt, Buildings, ListBullets, MapPin, Minus, Plus, Warning } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { BloqueDePaso, CheckoutSectionCard } from '@/components/checkout-section-card';
import { BotonPaso } from '@/components/checkout/boton-paso';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import { CAJA_CAMPO } from '@/components/checkout/estilos';
import { SelectPersonalizado } from '@/components/checkout/select-personalizado';
import { FieldPopover } from '@/components/field-popover';
import { PeopleStepper } from '@/components/people-stepper';
import type { Aeropuerto, Moneda, PaqueteServicioCatalogo, PuntoEncuentro, Zona } from '@/lib/api';
import { fechaDeComponente, sumarDias } from '@/lib/calendario-paquete';
import { fromLocalISODate } from '@/lib/dates';
import { intlLocale } from '@/lib/intl';
import { aMoneda } from '@/lib/moneda';
import { cantidadEfectiva, separarPersonalizaciones, type SeleccionPersonalizacion } from '@/lib/personalizaciones';
import { formatearPrecio } from '@/lib/pricing-paquete';
import type { ComponentePedido, DetalleTraslado } from '@/lib/pedido-payload';
import { TipoTrasladoCards } from '@/components/checkout/tipo-traslado-cards';
import { Despliegue } from '@/components/checkout/despliegue';
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
  conEncabezadoEmpresa: boolean;
  nombreEmpresa: string;
  moneda: Moneda;
  tipoCambio: string;
  inicio: string | null;
  noches: number | null;
  salida: string | null;
  puntos: PuntoEncuentro[];
  estadoTarjeta: 'activo' | 'editando' | 'completado' | 'suspendido';
  onAccion: () => void;
  onCompletar: () => void;
  onTope?: () => void;
  onPersonas: (personas: number) => void;
  onExtras: (seleccion: SeleccionPersonalizacion[]) => void;
  onTraslado: (cambios: Partial<DetalleTraslado>) => void;
};

export function GrupoServicio({
  lang, dict, componente, precioDependeDePersonas, esActividadPrincipal, personasMax, trasladoFijo, estado, conEncabezadoEmpresa, nombreEmpresa, moneda, tipoCambio,
  inicio, noches, salida, puntos, estadoTarjeta,
  onAccion, onCompletar, onTope, onPersonas, onExtras, onTraslado,
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
  const resumen = precioDependeDePersonas
    ? personasTexto
    : `${estado.personas} ${estado.personas === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`;
  const { obligatorias, opcionales } = separarPersonalizaciones(servicio.personalizaciones);
  const renderExtra = (extra: (typeof servicio.personalizaciones)[number]) => {
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
        <Despliegue abierto={!marcada && Boolean(extra.aviso_reforzado)}>
          <div className="flex items-start gap-2 border border-t-0 border-action/40 bg-action/10 px-4 py-2.5 text-xs text-foreground">
            <Warning size={14} className="mt-0.5 shrink-0 text-action" />
            <p>{checkout.amenitiesModal.reinforcedWarning}</p>
          </div>
        </Despliegue>
        <Despliegue abierto={marcada && Boolean(extra.cantidad_editable) && estado.personas > 1}>
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
            sinRespuestaLabel="—"
            opciones={extra.opciones_seleccion.map((opcion) => ({ valor: opcion, etiqueta: opcion }))}
            onChange={(valor) => actualizarExtra(extra.id, valor ? { id: extra.id, respuesta: valor } : undefined)}
          />
        </div>
      );
    }

    return (
      <label key={extra.id} htmlFor={id} className="flex flex-col gap-2 text-sm text-foreground">
        <span className="font-medium">{extra.nombre}{extra.obligatorio ? ' *' : ''}</span>
        <input id={id} type={extra.tipo_interaccion === 'input_numero' ? 'number' : 'text'}
          step={extra.tipo_interaccion === 'input_numero' ? 'any' : undefined}
          value={seleccion?.respuesta ?? ''} disabled={bloqueado}
          onChange={(event) => actualizarExtra(extra.id, event.target.value ? { id: extra.id, respuesta: event.target.value } : undefined)}
          className="border border-border bg-surface px-4 py-3 outline-none focus:border-accent" />
      </label>
    );
  };

  return (
    <CheckoutSectionCard
      title={servicio.nombre}
      etiqueta={conEncabezadoEmpresa ? nombreEmpresa : undefined}
      estado={estadoTarjeta}
      resumen={resumen}
      actionLabel={estadoTarjeta === 'completado' ? checkout.changeStep : estadoTarjeta === 'editando' ? checkout.doneEditing : undefined}
      onAction={estadoTarjeta === 'activo' ? undefined : onAccion}
      pie={estadoTarjeta === 'activo' ? (
        <BotonPaso onClick={onCompletar}>{checkout.confirmStep}</BotonPaso>
      ) : undefined}
    >
      {traslado && trasladoFijo && (
        <BloqueDePaso>
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

          <div className="flex flex-col gap-3 pt-5">
            <Despliegue abierto={traslado.modo === 'catalogo'}>
              <div className={CAJA_CAMPO}>
                <FieldPopover
                  compacto
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
                      {/* La otra dirección es una opción más de ESTA pregunta: va donde el
                          cliente ya está buscando, no como un enlace suelto en la tarjeta. */}
                      <button type="button"
                        onClick={() => { onTraslado({ modo: 'personalizada' }); cerrar(); }}
                        className="mt-1 flex w-full items-center gap-2 rounded-lg border-t border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-background">
                        <MapPin size={16} className="shrink-0 text-muted" />
                        {traslados.fields.otraDireccionOpcion}
                      </button>
                    </div>
                  )}
                </FieldPopover>
              </div>
            </Despliegue>
            <Despliegue abierto={traslado.modo !== 'catalogo'}>
              <div className="flex flex-col gap-3">
                <label className="flex flex-col gap-1.5 text-sm">
                  <span className="text-muted">{traslados.fields.otraDireccion}</span>
                  <span className="relative">
                    <MapPin size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                    <input type="text" value={traslado.direccion}
                      onChange={(event) => onTraslado({ direccion: event.target.value })}
                      placeholder={traslados.fields.direccionPlaceholder}
                      className={`w-full ${CAJA_CAMPO} py-3 pr-4 pl-11 text-sm text-foreground outline-none focus:border-accent`} />
                  </span>
                </label>
                <AccionTexto icono={<ListBullets size={14} />} onClick={() => onTraslado({ modo: 'catalogo' })}>
                  {traslados.fields.volverALista}
                </AccionTexto>
                <Despliegue abierto={traslado.tipo === 'redondo_actividad'}>
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
                </Despliegue>
              </div>
            </Despliegue>

            <Despliegue abierto={traslado.tipo === 'redondo_actividad' && traslado.modo === 'catalogo' && traslado.puntoEncuentroId !== null}>
              <p className="text-xs text-muted">
                {traslados.fields.zona}: {puntos.find((p) => p.id === traslado.puntoEncuentroId)?.zona === 'centro'
                  ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
              </p>
            </Despliegue>

          </div>
        </div>
      )}

      {/* Lo prellenado va al final y callado: llega resuelto del paso anterior, así
          que no merece ser lo primero que el cliente lee en la tarjeta. */}
      {esLogistica ? (
        <div className={CAJA_CAMPO}>
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
          <div className={CAJA_CAMPO}>
            <PeopleStepper
              compacto
              label={checkout.peopleLabel}
              maxNotice={booking.maxPeopleNotice}
              value={estado.personas}
              onChange={onPersonas}
              maxPeople={componente.personas_incluidas}
              minPeople={1}
              disabled={bloqueado}
              onMaxAttempt={onTope}
            />
          </div>
          <p className="mt-2 text-xs text-muted">
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
    </CheckoutSectionCard>
  );
}
