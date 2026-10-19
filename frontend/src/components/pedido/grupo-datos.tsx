'use client';

import { Buildings, ListBullets, MapPin } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { AccionTexto } from '@/components/checkout/accion-terciaria';
import { Despliegue } from '@/components/ui/despliegue';
import { CAJA_CONTENEDOR } from '@/components/ui/caja-campo';
import { FieldPopover } from '@/components/field-popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { PuntoEncuentro, Zona } from '@/lib/api';
import type { DetalleTraslado } from '@/lib/pedido-payload';

type Props = {
  traslados: Dictionary['traslados'];
  traslado: DetalleTraslado;
  /** Slug del servicio: nombra el grupo de radios de la zona. */
  servicioSlug: string;
  puntos: PuntoEncuentro[];
  onTraslado: (cambios: Partial<DetalleTraslado>) => void;
};

/**
 * Mitad "datos" de la tarjeta de un servicio con traslado propio: dónde lo
 * recogen (punto de encuentro o dirección escrita) y la zona. Sin estado
 * propio: el traslado vive en el reducer del pedido, así que plegar la
 * tarjeta no pierde lo elegido. Lo pinta `GrupoViaje` dentro de su bloque del
 * traslado (prop `datos`), después del tipo y del regreso.
 */
export function GrupoDatos({ traslados, traslado, servicioSlug, puntos, onTraslado }: Props) {
  return (
    <div className="flex flex-col gap-3 pt-5">
      <Despliegue abierto={traslado.modo === 'catalogo'}>
        <div className={CAJA_CONTENEDOR}>
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
                  <Button key={punto.id} variante="libre" type="button"
                    onClick={() => { onTraslado({ puntoEncuentroId: punto.id }); cerrar(); }}
                    className={`flex w-full items-center justify-between rounded-campo px-3 py-2 text-left text-sm transition-colors ${
                      punto.id === traslado.puntoEncuentroId ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground hover:bg-cafe-bruma'
                    }`}>
                    <span className="truncate pr-2">{punto.nombre}</span>
                  </Button>
                ))}
                {/* La otra dirección es una opción más de ESTA pregunta: va donde el
                    cliente ya está buscando, no como un enlace suelto en la tarjeta. */}
                <Button variante="libre" type="button"
                  onClick={() => { onTraslado({ modo: 'personalizada' }); cerrar(); }}
                  className="mt-1 flex w-full items-center gap-2 rounded-campo border-t border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-cafe-bruma">
                  <MapPin size={16} className="shrink-0 text-muted" />
                  {traslados.fields.otraDireccionOpcion}
                </Button>
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
              <Input type="text" value={traslado.direccion}
                onChange={(event) => onTraslado({ direccion: event.target.value })}
                placeholder={traslados.fields.direccionPlaceholder}
                className="pl-11" />
            </span>
          </label>
          <AccionTexto icono={<ListBullets size={14} />} onClick={() => onTraslado({ modo: 'catalogo' })}>
            {traslados.fields.volverALista}
          </AccionTexto>
          <Despliegue abierto={traslado.tipo === 'redondo_actividad'}>
            <fieldset className="grid grid-cols-2 gap-3">
              <legend className="sr-only">{traslados.fields.zona}</legend>
              {(['centro', 'periferia'] as Zona[]).map((zona) => (
                <label key={zona} className={`flex cursor-pointer items-center gap-2 rounded-campo border p-3 text-sm ${
                  traslado.zonaLibre === zona ? 'border-cafe-medio bg-cafe-bruma font-medium' : 'border-border text-muted'
                }`}>
                  <Input aspecto="heredado" type="radio" name={`zona-${servicioSlug}`} checked={traslado.zonaLibre === zona}
                    onChange={() => onTraslado({ zonaLibre: zona })} className="h-4 w-4 accent-accent" />
                  {zona === 'centro' ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
                </label>
              ))}
            </fieldset>
          </Despliegue>
        </div>
      </Despliegue>

      <Despliegue abierto={traslado.tipo === 'redondo_actividad' && traslado.modo === 'catalogo' && traslado.puntoEncuentroId !== null}>
        <p className="text-sm text-muted">
          {traslados.fields.zona}: {puntos.find((p) => p.id === traslado.puntoEncuentroId)?.zona === 'centro'
            ? traslados.fields.zonaCentro : traslados.fields.zonaPeriferia}
        </p>
      </Despliegue>

    </div>
  );
}
