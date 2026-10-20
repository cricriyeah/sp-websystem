import type { ComponentType, ReactNode } from 'react';
import type { IconProps } from '@phosphor-icons/react';
import { Bed, Boat, Compass, FishSimple, Package } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import type { SedeDestacada } from '@/content/sedes-tipos';
import { getEmpresa } from '@/content/empresas';
import { claveDePaquete, claveDeServicio, fotosDeGrupo, imagenDeCatalogo } from '@/content/imagenes-catalogo';
import {
  ORDEN_GRUPOS,
  baseDeCobro,
  chipDePaquete,
  chipDeServicio,
  grupoDePaquete,
  grupoDeServicio,
  plantillaDeGrupo,
  type GrupoCatalogo,
} from '@/lib/etiquetas-catalogo';
import type { Seccion } from '@/lib/secciones-sede';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { hrefDetalleServicio, hrefPaquete } from '@/lib/booking-href';
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { hrefSede } from '@/lib/routes';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { TarjetaServicio, type VistaTarjeta } from '@/components/tarjeta-servicio';
import { AvisoEstado } from '@/components/ui/aviso-estado';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';
import { cn } from '@/components/ui/cn';

type Textos = Dictionary['sedeContenido']['queReservar'];

type Props = {
  lang: Locale;
  moneda: Moneda;
  sede: { slug: string; nombre: string };
  /** `null` = el catálogo no respondió. */
  servicios: ServicioCatalogo[] | null;
  paquetes: PaqueteCatalogo[] | null;
  estado: NonNullable<Seccion['estado']>;
  destacadas: SedeDestacada[];
  textos: Textos;
  fondo: Fondo;
  borde: boolean;
};

const ICONO_GRUPO: Record<GrupoCatalogo, ComponentType<IconProps>> = {
  paquetes: Package,
  pesca: FishSimple,
  paseos: Compass,
  estancia: Bed,
};

const TITULO_GRUPO = {
  paquetes: 'grupoPaquetes',
  pesca: 'grupoPesca',
  paseos: 'grupoPaseos',
  estancia: 'grupoEstancia',
} as const satisfies Record<GrupoCatalogo, keyof Textos>;

type Elemento = { grupo: GrupoCatalogo; vista: VistaTarjeta; destacada: boolean };

/** En `/en` el precio va primero en dólares y debajo, aproximado, en pesos. */
function precioDe(mxn: (moneda: Moneda) => number | null, lang: Locale, moneda: Moneda) {
  const principal: Moneda = lang === 'en' ? 'USD' : moneda;
  const monto = `${formatearPrecio(mxn(principal), principal)} ${principal}`;
  const aprox = principal === 'USD' ? `≈ ${formatearPrecio(mxn('MXN'), 'MXN')} MXN` : undefined;
  return { monto, aprox };
}

function vistaDeServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda, sedeSlug: string): VistaTarjeta {
  const clave = claveDeServicio(servicio.empresa_slug, servicio.slug);
  const empresa = getEmpresa(servicio.empresa_slug);
  const base = servicio.tipo_servicio === 'transporte' ? baseDeCobro('por_ruta', lang) : baseDeCobro(servicio.estrategia_precio, lang);
  const porRuta = !base || !base.conDesde;
  return {
    clave,
    nombre: servicio.nombre,
    empresa: { nombre: empresa?.nombre ?? servicio.empresa_slug, logo: empresa?.logo },
    chip: grupoDeServicio(servicio) === 'estancia' ? null : chipDeServicio(servicio, lang),
    foto: imagenDeCatalogo(clave, lang),
    precio: porRuta
      ? null
      : { ...precioDe((m) => aMoneda(servicio.precio_base, m, servicio.tipo_cambio_usd), lang, moneda), base: base.texto, conDesde: true },
    capacidad: servicio.capacidad_maxima ?? null,
    incluye: servicio.incluye?.[lang] ?? [],
    hrefDetalle: hrefDetalleServicio(servicio, lang, moneda, sedeSlug),
  };
}

function vistaDePaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): VistaTarjeta {
  const clave = claveDePaquete(paquete.slug);
  const empresa = getEmpresa(paquete.empresa_lider_slug);
  const base = baseDeCobro(paquete.estrategia_precio, lang);
  const propio = paquete.incluye?.[lang] ?? [];
  // Sin lista propia: la de sus servicios, cada renglón con el nombre del servicio.
  const incluye = propio.length > 0
    ? propio
    : [...paquete.servicios_asociados]
        .sort((a, b) => a.orden - b.orden)
        .flatMap((c) => (c.servicio.incluye?.[lang] ?? []).map((renglon) => `${c.servicio.nombre}: ${renglon}`));
  return {
    clave,
    nombre: paquete.nombre,
    empresa: { nombre: empresa?.nombre ?? paquete.empresa_lider, logo: empresa?.logo },
    chip: chipDePaquete(paquete, lang),
    foto: imagenDeCatalogo(clave, lang),
    precio: base
      ? { ...precioDe((m) => calcularPrecioPaquete(paquete, m).precioFinal, lang, moneda), base: base.texto, conDesde: base.conDesde }
      : null,
    capacidad: null,
    incluye,
    hrefDetalle: hrefPaquete(paquete, lang, moneda),
  };
}

/** Clases de cada celda según la plantilla del grupo; en 768 px la última de un número impar ocupa 2. */
function claseCelda(i: number, n: number, destacada: ReturnType<typeof plantillaDeGrupo>['destacada']) {
  return cn(
    n > 1 && n % 2 === 1 && i === n - 1 && 'md:col-span-2 lg:col-span-1',
    i === 0 && destacada === 'cuadrada' && 'lg:col-span-2 lg:row-span-2',
    i === 0 && destacada === 'ancha' && 'lg:col-span-2',
  );
}

/**
 * «Qué puedes reservar»: servicios y paquetes de la sede en un solo bloque, por grupo, con lo
 * que cada uno incluye y quién lo opera. Proyecta en servidor la respuesta de la API a lo mínimo
 * que pinta la tarjeta. Con el catálogo caído o vacío pinta su estado, nunca «pronto».
 *
 * Server Component.
 */
export function QuePuedesReservar({ lang, moneda, sede, servicios, paquetes, estado, destacadas, textos, fondo, borde }: Props) {
  const contacto = tieneWhatsapp ? whatsappHref(textos.whatsappMensaje.replace('{sede}', sede.nombre)) : null;
  const shell = (contenido: ReactNode) => (
    <SectionShell
      id={ANCLA_DE.reservar}
      fondo={fondo}
      borde={borde}
      regla
      titulo={textos.titulo}
      lado={<p className="max-w-[46ch] texto-cuerpo text-muted lg:pb-2">{textos.subtexto}</p>}
    >
      {contenido}
    </SectionShell>
  );

  if (estado === 'catalogo_caido') {
    return shell(
      <AvisoEstado tono="error" className="mt-8">
        <p className="font-semibold">{textos.caido}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <a href={hrefSede(lang, sede.slug, ANCLA_DE.reservar)} className={botonClases({ variante: 'secundario' })}>{textos.reintentar}</a>
          {contacto && <a href={contacto} target="_blank" rel="noopener noreferrer" className={botonClases({ variante: 'secundario' })}>{textos.whatsapp}</a>}
        </div>
      </AvisoEstado>,
    );
  }

  if (estado === 'vacio') {
    return shell(
      <div className="mt-8 flex flex-col items-start gap-4 rounded-card border border-borde bg-superficie p-6">
        <Boat size={32} aria-hidden="true" className="text-apagado" />
        <p className="texto-cuerpo text-foreground">{textos.vacio}</p>
        {contacto && <a href={contacto} target="_blank" rel="noopener noreferrer" className={botonClases({ variante: 'secundario' })}>{textos.whatsapp}</a>}
      </div>,
    );
  }

  const primera = destacadas[0];
  const elementos: Elemento[] = [
    ...(paquetes ?? []).map((p) => ({
      grupo: grupoDePaquete(p),
      vista: vistaDePaquete(p, lang, moneda),
      destacada: primera?.tipo === 'paquete' && primera.slug === p.slug,
    })),
    ...(servicios ?? []).map((s) => ({
      grupo: grupoDeServicio(s),
      vista: vistaDeServicio(s, lang, moneda, sede.slug),
      destacada: primera?.tipo === 'servicio' && primera.slug === s.slug && (!primera.empresaSlug || primera.empresaSlug === s.empresa_slug),
    })),
  ];
  // El grupo de estancia se nombra por lo que trae: en La Paz solo hay traslados y en La Ventana solo hospedaje.
  const estancia = (servicios ?? []).filter((s) => grupoDeServicio(s) === 'estancia');
  const conHospedaje = estancia.some((s) => s.tipo_servicio === 'hospedaje');
  const conTraslados = estancia.some((s) => s.tipo_servicio !== 'hospedaje');
  const tituloEstancia = conHospedaje && conTraslados ? textos.grupoEstancia : conHospedaje ? textos.grupoHospedaje : textos.grupoTraslados;
  let fotosPintadas = 0;

  return shell(
    <div className="mt-10 flex flex-col gap-12">
      {ORDEN_GRUPOS.map((grupo) => {
        // La destacada abre su grupo; el resto conserva el orden del catálogo.
        const delGrupo = elementos.filter((e) => e.grupo === grupo).sort((a, b) => Number(b.destacada) - Number(a.destacada));
        if (delGrupo.length === 0) return null;
        const n = delGrupo.length;
        const plantilla = plantillaDeGrupo(n);
        const conFoto = fotosDeGrupo(delGrupo.map((e) => e.vista.clave));
        const Icono = ICONO_GRUPO[grupo];
        const sizes = plantilla.columnas === 1 ? '(min-width: 640px) 288px, 100vw' : '(min-width: 1024px) 33vw, (min-width: 768px) 50vw, 100vw';
        return (
          <div key={grupo}>
            <h3 className="flex items-center gap-2 texto-subtitulo text-foreground">
              <Icono size={20} aria-hidden="true" className="shrink-0 text-tinta-suave" />
              {grupo === 'estancia' ? tituloEstancia : textos[TITULO_GRUPO[grupo]]}
            </h3>
            <div className={cn('mt-6 grid gap-6', n === 1 ? 'max-w-[720px]' : plantilla.columnas === 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 lg:grid-cols-3')}>
              {delGrupo.map((e, i) => {
                const vista = conFoto ? e.vista : { ...e.vista, foto: null };
                const prioridad = Boolean(vista.foto) && fotosPintadas++ < 2;
                const destacada = i === 0 && plantilla.destacada !== 'ninguna' ? (plantilla.destacada === 'horizontal' ? 'horizontal' : 'lateral') : undefined;
                return (
                  <TarjetaServicio
                    key={vista.clave}
                    vista={vista}
                    textos={textos}
                    hrefContacto={contacto}
                    destacada={destacada}
                    prioridad={prioridad}
                    sizes={sizes}
                    className={claseCelda(i, n, plantilla.destacada)}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
    </div>,
  );
}
