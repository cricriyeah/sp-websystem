'use client';

import { Buildings, ListBullets, MapPin } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import { Despliegue } from '@/components/ui/despliegue';
import { CAJA_CONTENEDOR } from '@/components/ui/caja-campo';
import { ErrorDeCampo } from '@/components/ui/error-de-campo';
import { FieldPopover } from '@/components/field-popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { PuntoEncuentro, TipoTraslado, Zona } from '@/lib/api';

type Props = {
  traslados: Dictionary['traslados'];
  puntosEncuentro: PuntoEncuentro[];
  puntoSeleccionado: PuntoEncuentro | undefined;
  puntoEncuentroId: number | null;
  modoHospedaje: 'catalogo' | 'personalizada';
  direccionPersonalizada: string;
  zonaPersonalizada: Zona | '';
  tipoTraslado: TipoTraslado;
  /** Error de la tarjeta de recogida (hotel o dirección). */
  error: string;
  onPunto: (id: number) => void;
  onOtraDireccion: () => void;
  onDireccion: (valor: string) => void;
  onVolverALista: () => void;
  onZona: (zona: Zona) => void;
};

/**
 * Contenido del paso de recogida de traslados: hotel o punto de encuentro (con
 * "otra dirección" como última opción), dirección manual y zona. Sin estado
 * propio: modo, punto, dirección y zona viven en `TrasladoView` (la tarifa, el
 * payload y la recuperación los leen), así que plegar la tarjeta no pierde nada.
 */
export function BloqueRecogida({
  traslados,
  puntosEncuentro,
  puntoSeleccionado,
  puntoEncuentroId,
  modoHospedaje,
  direccionPersonalizada,
  zonaPersonalizada,
  tipoTraslado,
  error,
  onPunto,
  onOtraDireccion,
  onDireccion,
  onVolverALista,
  onZona,
}: Props) {
  return (
    <>
      <div className="flex flex-col gap-3">
        <Despliegue abierto={modoHospedaje === 'catalogo'}>
          <div className={CAJA_CONTENEDOR}>
            <FieldPopover
              compacto
              label={traslados.fields.puntoEncuentro}
              value={puntoSeleccionado?.nombre ?? ''}
              vacio={puntoEncuentroId === null}
              placeholder={traslados.fields.puntoEncuentroPlaceholder}
              icon={<Buildings size={20} className="shrink-0 text-muted" />}
            >
              {(cerrar) => (
                <div className="max-h-72 w-full overflow-y-auto sm:w-80">
                  {puntosEncuentro.map((punto) => (
                    <Button
                      key={punto.id}
                      variante="libre"
                      type="button"
                      onClick={() => {
                        onPunto(punto.id);
                        cerrar();
                      }}
                      className={`flex w-full items-center justify-between rounded-campo px-3 py-2 text-left text-sm transition-colors ${
                        punto.id === puntoEncuentroId
                          ? 'bg-accent font-medium text-accent-foreground'
                          : 'text-foreground hover:bg-cafe-bruma'
                      }`}
                    >
                      <span className="truncate pr-2">{punto.nombre}</span>
                      <span className="shrink-0 texto-pie font-medium opacity-75">
                        {punto.zona}
                      </span>
                    </Button>
                  ))}
                  {/* La otra dirección es una opción más de ESTA pregunta. */}
                  <Button
                    variante="libre"
                    type="button"
                    onClick={() => {
                      onOtraDireccion();
                      cerrar();
                    }}
                    className="mt-1 flex w-full items-center gap-2 rounded-campo border-t border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-cafe-bruma"
                  >
                    <MapPin size={16} className="shrink-0 text-muted" />
                    {traslados.fields.otraDireccionOpcion}
                  </Button>
                </div>
              )}
            </FieldPopover>
          </div>
        </Despliegue>

        <Despliegue abierto={modoHospedaje !== 'catalogo'}>
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">{traslados.fields.otraDireccion}</span>
              <span className="relative">
                <MapPin size={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted" />
                <Input
                  type="text"
                  value={direccionPersonalizada}
                  onChange={(e) => onDireccion(e.target.value)}
                  placeholder={traslados.fields.direccionPlaceholder}
                  className="pl-11"
                />
              </span>
            </label>
            <AccionTexto
              icono={<ListBullets size={14} />}
              onClick={() => onVolverALista()}
            >
              {traslados.fields.volverALista}
            </AccionTexto>
            <Despliegue abierto={tipoTraslado === 'redondo_actividad'}>
              <fieldset className="grid grid-cols-2 gap-3">
                <legend className="sr-only">{traslados.fields.zona}</legend>
                {(['centro', 'periferia'] as const).map((z) => (
                  <label
                    key={z}
                    className={`flex cursor-pointer items-center gap-2 rounded-campo border p-3 text-sm ${
                      zonaPersonalizada === z ? 'border-accent bg-cafe-bruma font-medium' : 'border-border text-muted'
                    }`}
                  >
                    <Input
                      aspecto="heredado"
                      type="radio"
                      name="zona-personalizada"
                      value={z}
                      checked={zonaPersonalizada === z}
                      onChange={() => onZona(z)}
                      className="h-4 w-4 accent-accent"
                    />
                    {z === 'centro' ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
                  </label>
                ))}
              </fieldset>
              <p className="mt-2 text-xs text-muted">{traslados.fields.zonaRequiredNotice}</p>
            </Despliegue>
          </div>
        </Despliegue>

        <Despliegue abierto={tipoTraslado === 'redondo_actividad' && modoHospedaje === 'catalogo' && puntoEncuentroId !== null}>
          <p className="text-xs text-muted">
            {traslados.fields.zona}: {puntoSeleccionado?.zona === 'centro'
              ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
          </p>
        </Despliegue>
      </div>
      <ErrorDeCampo id="error-recogida" mensaje={error} />
    </>
  );
}
