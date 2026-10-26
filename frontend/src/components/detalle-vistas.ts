// Arma lo que pinta `DetalleProducto` (F10) para un servicio o para un paquete, desde la respuesta de la API, el
// diccionario y el contenido de la sede. Aquí viven los casos de borde del servicio: la pesca de Sal y Sol y el
// traslado conservan su página aunque el catálogo no responda. Solo corre en servidor.
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo, ServicioPersonalizacionCatalogo } from '@/lib/api';
import type { SedeContenido } from '@/content/sedes-tipos';
import { getEmpresa } from '@/content/empresas';
import { claveDePaquete, claveDeServicio, galeriaDeCatalogo, imagenDeCatalogo } from '@/content/imagenes-catalogo';
import { palabraDePaquete, palabraDeServicio } from '@/lib/etiquetas-catalogo';
import { colorDePaquete, colorDeServicio } from '@/lib/color-actividad';
import { hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { hrefInicio, hrefSede } from '@/lib/routes';
import { ANCLA_DE, ANCLA_HUB } from '@/lib/secciones-sede';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import type { BloqueLista, DatoFicha, ExtraDetalle, ItemLista, TextosDetalle, VistaDetalle } from '@/components/detalle-producto';
import type { VistaEmpresa } from '@/components/tarjeta-empresa';
import { vistaDeEmpresa } from '@/components/vistas-empresa';
import { esExclusion, vistaDePaquete, vistaDeServicio } from '@/components/vistas-catalogo';

type Comun = {
  lang: Locale;
  moneda: Moneda;
  dict: Dictionary;
  sede: SedeContenido | undefined;
  /** El resto del catálogo de la sede, para «También en»; `null` si no respondió. */
  otros: { servicios: ServicioCatalogo[] | null; paquetes: PaqueteCatalogo[] | null };
};

/** «+$450 MXN» y, aparte, «por persona» si el extra se cobra por cada una. */
function precioDeExtra(extra: ServicioPersonalizacionCatalogo, tipoCambio: string, { moneda, dict }: Comun) {
  const detalle = dict.sedeContenido.detalle;
  if (!(Number(extra.precio) > 0)) return { monto: dict.serviceDetail.optionalPrice };
  return {
    monto: detalle.extraPrecio.replace('{monto}', `${formatearPrecio(aMoneda(extra.precio, moneda, tipoCambio), moneda)} ${moneda}`),
    base: extra.cobrar_por_persona ? detalle.porPersona : undefined,
  };
}

function extrasDe(servicios: ServicioCatalogo[], comun: Comun): ExtraDetalle[] {
  const vistos = new Set<number>();
  const extras: ExtraDetalle[] = [];
  for (const servicio of servicios) {
    for (const extra of servicio.personalizaciones) {
      if (extra.obligatorio || vistos.has(extra.personalizacion_id)) continue;
      vistos.add(extra.personalizacion_id);
      extras.push({
        nombre: extra.nombre,
        detalle: extra.descripcion?.[comun.lang] || undefined,
        precio: precioDeExtra(extra, servicio.tipo_cambio_usd, comun),
      });
    }
  }
  return extras;
}

/** El «incluye» del backoffice, con las exclusiones («el hospedaje no incluye comida») aparte. */
function partirIncluye(renglones: string[]) {
  return { incluye: renglones.filter((r) => !esExclusion(r)), noIncluye: renglones.filter(esExclusion) };
}

/** Cuánto suma cada persona extra, en la moneda de la página; `null` si no suma nada. */
function notaDeExtra(incluidas: number, extra: string, tipoCambio: string, maximo: number | null | undefined, { moneda, dict }: Comun): string | undefined {
  if (!(Number(extra) > 0)) return undefined;
  const detalle = dict.sedeContenido.detalle;
  const monto = `${formatearPrecio(aMoneda(extra, moneda, tipoCambio), moneda)} ${moneda}`;
  const base = maximo ? detalle.notaExtraMax.replace('{max}', String(maximo)) : detalle.notaExtra;
  return base.replace('{n}', String(incluidas)).replace('{monto}', monto);
}

function datosDePago(permiteAnticipo: boolean, porcentaje: number, { dict }: Comun) {
  const detalle = dict.sedeContenido.detalle;
  return {
    etiqueta: detalle.etiquetaPago,
    valor: permiteAnticipo && porcentaje > 0 ? detalle.pagoAnticipo.replace('{porcentaje}', String(porcentaje)) : detalle.pagoTotal,
  };
}

function volverASede({ lang, dict, sede }: Comun) {
  return sede
    ? { href: hrefSede(lang, sede.slug, ANCLA_DE.reservar), etiqueta: dict.sedeContenido.detalle.verSede.replace('{sede}', sede.nombre) }
    : { href: hrefInicio(lang, ANCLA_HUB.sedes), etiqueta: dict.serviceDetail.backToServices };
}

function empresasDe(slugs: string[], { lang, sede }: Comun): VistaEmpresa[] {
  const enlaces = sede ? [{ nombre: sede.nombre, href: hrefSede(lang, sede.slug, ANCLA_DE.reservar) }] : [];
  return [...new Set(slugs)].flatMap((slug) => {
    const empresa = getEmpresa(slug);
    return empresa && empresa.descripcion[lang].trim() !== '' ? [vistaDeEmpresa(empresa, lang, enlaces)] : [];
  });
}

function tambienDe(comun: Comun, quitar: (clave: string) => boolean) {
  const { lang, moneda, dict, sede, otros } = comun;
  if (!sede) return null;
  const detalle = dict.sedeContenido.detalle;
  const productos = [
    ...(otros.paquetes ?? []).map((p) => vistaDePaquete(p, lang, moneda)),
    ...(otros.servicios ?? []).map((s) => vistaDeServicio(s, lang, moneda, sede.slug)),
  ].filter((producto) => !quitar(producto.clave));
  return {
    titulo: detalle.tambienEn.replace('{sede}', sede.nombre),
    etiqueta: detalle.carril.replace('{sede}', sede.nombre),
    productos,
  };
}

type EntradaServicio = Comun & {
  empresaSlug: string;
  slug: string;
  /** `null` = el catálogo no respondió (la pesca de Sal y Sol y el traslado siguen teniendo página). */
  servicio: ServicioCatalogo | null;
  pesca: boolean;
  traslado: boolean;
};

export function vistaDeDetalleServicio(entrada: EntradaServicio): VistaDetalle {
  const { lang, moneda, dict, sede, empresaSlug, slug, servicio, pesca, traslado } = entrada;
  const detalle = dict.sedeContenido.detalle;
  const textos = dict.sedeContenido.queReservar;
  const tipo = servicio?.tipo_servicio ?? (traslado ? 'transporte' : pesca ? 'pesca' : 'paseo');
  const titulo = servicio?.nombre ?? (pesca ? dict.serviceDetail.fishingTitle : traslado ? dict.traslados.title : dict.serviceDetail.metaFallback);
  const lead = servicio?.descripcion
    || (pesca ? dict.serviceDetail.fishingDescription : traslado ? dict.traslados.subtitle : dict.serviceDetail.unavailableDescription);
  const nombreEmpresa = getEmpresa(empresaSlug)?.nombre ?? empresaSlug;
  const clave = claveDeServicio(empresaSlug, slug);

  // La lista propia del servicio; sin ella, la pesca y el traslado conservan lo que ya tenían escrito.
  const propia = partirIncluye(servicio?.incluye?.[lang] ?? []);
  const incluye: ItemLista[] = propia.incluye.length > 0
    ? propia.incluye.map((titulo) => ({ titulo }))
    : pesca
      ? dict.included.included.map((item) => ({ titulo: item.title, detalle: item.body }))
      : traslado
        ? [{ titulo: dict.traslados.summary.included }]
        : [];
  const otros: BloqueLista[] = [];
  if (pesca && propia.incluye.length === 0) otros.push({ titulo: dict.included.bringTitle, items: dict.included.bring.map((titulo) => ({ titulo })) });

  const vista = servicio ? vistaDeServicio(servicio, lang, moneda, sede?.slug ?? '') : null;
  const porGrupo = servicio?.estrategia_precio === 'por_grupo';
  // La ficha: lo que el turista busca primero, en grande. Solo lo que el servicio tiene.
  const ficha: DatoFicha[] = [
    ...(vista?.horario ? [{ etiqueta: detalle.ficha.salida, valor: vista.horario }] : []),
    ...(servicio?.duracion ? [{ etiqueta: detalle.ficha.duracion, valor: servicio.duracion }] : []),
    ...(servicio?.capacidad_maxima
      ? [{ etiqueta: detalle.ficha.personas, valor: detalle.ficha.hasta.replace('{n}', String(servicio.capacidad_maxima)) }]
      : []),
    ...(servicio?.punto_salida ? [{ etiqueta: detalle.ficha.salesDe, valor: servicio.punto_salida }] : []),
  ];
  // El cupo máximo ya va en la ficha: el bloque de compra se queda con quién, cuántos cubre el precio y cómo pagas.
  const datos = [
    { etiqueta: detalle.etiquetaOpera, valor: nombreEmpresa },
    ...(servicio && porGrupo ? [{ etiqueta: detalle.etiquetaIncluye, valor: detalle.personas.replace('{n}', String(servicio.personas_incluidas)) }] : []),
    ...(servicio ? [datosDePago(servicio.permite_anticipo, servicio.porcentaje_anticipo, entrada)] : []),
  ];
  const puedeReservar = servicio !== null || pesca || traslado;

  return {
    titulo,
    lead,
    color: servicio ? colorDeServicio(servicio) : colorDeServicio({ tipo_servicio: tipo }),
    palabra: palabraDeServicio(tipo, lang),
    foto: imagenDeCatalogo(clave, lang),
    galeria: galeriaDeCatalogo(clave, lang),
    linea: textos.opera.replace('{empresa}', nombreEmpresa),
    volver: volverASede(entrada),
    tituloQueEs: detalle.queEs,
    ficha,
    incluye: { titulo: detalle.queIncluye, items: incluye, noIncluye: propia.noIncluye },
    extras: { titulo: detalle.puedesAgregar, items: extrasDe(servicio ? [servicio] : [], entrada) },
    otros,
    preguntaIncluye: servicio && !traslado && !pesca && propia.incluye.length === 0 && tieneWhatsapp
      ? { etiqueta: textos.preguntaIncluye, href: whatsappHref(textos.whatsappMensaje.replace('{sede}', sede?.nombre ?? '')) }
      : null,
    compra: {
      precio: vista ? (vista.precio ?? 'ruta') : traslado ? 'ruta' : null,
      datos,
      nota: traslado
        ? dict.serviceDetail.transferInstructions
        : servicio && porGrupo ? notaDeExtra(servicio.personas_incluidas, servicio.precio_persona_extra, servicio.tipo_cambio_usd, servicio.capacidad_maxima, entrada) : undefined,
      href: puedeReservar
        ? hrefServicio(servicio ?? { slug, empresa_slug: empresaSlug, tipo_servicio: tipo }, lang, moneda, { origen: 'servicio', sede: sede?.slug })
        : null,
      etiquetaBoton: detalle.reservarServicio.replace('{nombre}', titulo),
    },
    empresas: empresasDe([empresaSlug], entrada),
    tambien: tambienDe(entrada, (c) => c === clave),
  };
}

type EntradaPaquete = Comun & { paquete: PaqueteCatalogo };

export function vistaDeDetallePaquete(entrada: EntradaPaquete): VistaDetalle {
  const { lang, moneda, dict, paquete } = entrada;
  const detalle = dict.sedeContenido.detalle;
  const textos = dict.sedeContenido.queReservar;
  const clave = claveDePaquete(paquete.slug);
  const componentes = [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden);
  const servicios = componentes.filter((c, i) => componentes.findIndex((o) => o.servicio_id === c.servicio_id) === i).map((c) => c.servicio);
  const slugsEmpresa = [paquete.empresa_lider_slug, ...servicios.map((s) => s.empresa_slug)];
  const nombresEmpresa = [...new Set(slugsEmpresa)].map((slug) => getEmpresa(slug)?.nombre ?? slug);

  // Lo que dice el paquete de sí mismo; sin lista propia, los servicios que lo forman con quién opera cada uno.
  const propia = partirIncluye(paquete.incluye?.[lang] ?? []);
  const incluye: ItemLista[] = propia.incluye.length > 0
    ? propia.incluye.map((titulo) => ({ titulo }))
    : servicios.map((s) => ({ titulo: s.nombre, detalle: textos.opera.replace('{empresa}', getEmpresa(s.empresa_slug)?.nombre ?? s.empresa_slug) }));

  const vista = vistaDePaquete(paquete, lang, moneda);
  const porGrupo = paquete.estrategia_precio === 'por_grupo';
  // La ficha del paquete: cuántas noches, cuántos días de mar y si te recogen en el aeropuerto.
  const salidasAlMar = componentes.find((c) => c.servicio.tipo_servicio === 'pesca' || c.servicio.tipo_servicio === 'paseo')?.salidas ?? 0;
  const conTraslado = componentes.some((c) => c.servicio.tipo_servicio === 'transporte');
  const ficha: DatoFicha[] = [
    ...(paquete.noches ? [{ etiqueta: detalle.ficha.estancia, valor: detalle.noches.replace('{n}', String(paquete.noches)) }] : []),
    ...(salidasAlMar > 0 ? [{ etiqueta: detalle.ficha.alMar, valor: detalle.ficha.salidas.replace('{n}', String(salidasAlMar)) }] : []),
    ...(conTraslado ? [{ etiqueta: detalle.ficha.recogida, valor: detalle.ficha.aeropuerto }] : []),
  ];
  const datos = [
    { etiqueta: detalle.etiquetaOpera, valor: nombresEmpresa.join(' · ') },
    ...(porGrupo ? [{ etiqueta: detalle.etiquetaIncluye, valor: detalle.personas.replace('{n}', String(paquete.personas_precio_base)) }] : []),
    datosDePago(paquete.permite_anticipo, paquete.porcentaje_anticipo, entrada),
  ];

  return {
    titulo: paquete.nombre,
    lead: paquete.descripcion,
    color: colorDePaquete(paquete),
    palabra: palabraDePaquete(paquete.noches, lang),
    foto: imagenDeCatalogo(clave, lang),
    galeria: galeriaDeCatalogo(clave, lang),
    linea: textos.opera.replace('{empresa}', nombresEmpresa.join(' · ')),
    volver: volverASede(entrada),
    tituloQueEs: detalle.queEsPaquete,
    ficha,
    incluye: { titulo: detalle.queIncluyePaquete, items: incluye, noIncluye: propia.noIncluye },
    extras: { titulo: detalle.puedesAgregar, items: extrasDe(servicios, entrada) },
    otros: [],
    preguntaIncluye: null,
    compra: {
      precio: vista.precio,
      datos,
      nota: paquete.es_cruza_empresa
        ? detalle.cobroPorEmpresa
        : porGrupo ? notaDeExtra(paquete.personas_precio_base, paquete.precio_persona_extra, paquete.tipo_cambio_usd, undefined, entrada) : undefined,
      href: hrefPaquete(paquete, lang, moneda),
      etiquetaBoton: detalle.reservarServicio.replace('{nombre}', paquete.nombre),
    },
    empresas: empresasDe(slugsEmpresa, entrada),
    tambien: tambienDe(entrada, (c) => c === clave),
  };
}

/** Los textos fijos del detalle, del diccionario de la página. */
export function textosDeDetalle(dict: Dictionary): TextosDetalle {
  const reservar = dict.sedeContenido.queReservar;
  return {
    detalle: dict.sedeContenido.detalle,
    visor: dict.sedeContenido.galeriaVisor,
    reservar: { ...reservar, reservarAria: reservar.verYReservarAria },
    carril: { anterior: reservar.flechaAnterior, siguiente: reservar.flechaSiguiente },
    empresa: dict.hubContenido,
    reservarCorto: reservar.reservar,
    desde: reservar.desde,
    tarifaRuta: reservar.tarifaRuta,
  };
}
