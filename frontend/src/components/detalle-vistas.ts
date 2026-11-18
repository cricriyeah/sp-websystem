// Arma lo que pinta `DetalleProducto` (F10) para un servicio o para un paquete, desde la respuesta de la API, el
// diccionario y el contenido de la sede. Aquí viven los casos de borde del servicio: la pesca de Sal y Sol y el
// traslado conservan su página aunque el catálogo no responda. Solo corre en servidor.
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo, ServicioPersonalizacionCatalogo } from '@/lib/api';
import type { SedeContenido } from '@/content/sedes-tipos';
import { getEmpresa } from '@/content/empresas';
import { bloquesDeDetalle } from '@/content/detalle-extra';
import { conCatalogo } from '@/lib/catalogo-en-texto';
import { equipoDeServicio, especiesDeServicio, reglasDeServicio } from '@/content/datos-servicio';
import { getGuia, slugEnIdioma } from '@/content/guias';
import { condicionesDeCompra, enlaceAlMapa, etiquetasDeReglas, type ClaseDeCompra } from '@/lib/detalle-servicio';
import { seoDePaquete, seoDeServicio } from '@/content/seo-detalle';
import { claveDePaquete, claveDeServicio, galeriaDeCatalogo, imagenDeCatalogo, imagenesDeCatalogo } from '@/content/imagenes-catalogo';
import { palabraDePaquete, palabraDeServicio } from '@/lib/etiquetas-catalogo';
import { colorDePaquete, colorDeServicio } from '@/lib/color-actividad';
import { hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { aMoneda } from '@/lib/moneda';
import { precioPublico } from '@/lib/iva';
import { hrefGuia, hrefSede } from '@/lib/routes';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import type { BloqueLista, DatoFicha, EtiquetaDetalle, ExtraDetalle, ItemLista, TextosDetalle, VistaDetalle, VistaQuien } from '@/components/detalle-producto';
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
    monto: detalle.extraPrecio.replace('{monto}', `${formatearPrecio(precioPublico(aMoneda(extra.precio, moneda, tipoCambio)), moneda)} ${moneda}`),
    base: extra.cobrar_por_persona ? detalle.porPersona : undefined,
  };
}

function extrasDe(servicios: ServicioCatalogo[], comun: Comun, enFicha: ReadonlySet<number> = new Set()): ExtraDetalle[] {
  const vistos = new Set<number>(enFicha);
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
  const monto = `${formatearPrecio(precioPublico(aMoneda(extra, moneda, tipoCambio)), moneda)} ${moneda}`;
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

/** «Reserva con tranquilidad» del bloque de compra, con el plazo de lo que se compra y el enlace a la política. */
function condicionesDe(clase: ClaseDeCompra, alMar: boolean, { lang, dict }: Comun): VistaDetalle['compra']['condiciones'] {
  const textos = dict.sedeContenido.detalle.condiciones;
  return {
    titulo: textos.titulo,
    renglones: condicionesDeCompra(clase, alMar, textos),
    enlace: { href: `/${lang}/cancelaciones`, etiqueta: textos.enlace },
  };
}

/** Las especies del servicio; la que tiene guía enlaza a la de su idioma. */
function especiesDe(clave: string, { lang }: Comun): EtiquetaDetalle[] {
  return especiesDeServicio(clave).map((especie) => {
    const slug = especie.guia && (lang === 'es' ? especie.guia : slugEnIdioma(especie.guia, lang));
    return { texto: especie.nombre[lang], href: slug && getGuia(slug, lang) ? hrefGuia(lang, slug) : undefined };
  });
}

/**
 * La licencia de pesca, en la ficha y no como algo que «puedes sumar» (PFD del detalle, 2026-11-17): es obligatoria para
 * cada quien que pesca. Su precio es el del extra del backoffice.
 */
function licenciaDe(servicio: ServicioCatalogo | null, comun: Comun): { dato: DatoFicha; id: number } | null {
  const licencia = servicio?.personalizaciones.find((p) => p.tipo === 'licencia' && !p.obligatorio && Number(p.precio) > 0);
  if (!servicio || !licencia) return null;
  const { moneda, dict } = comun;
  const ficha = dict.sedeContenido.detalle.ficha;
  const monto = `${formatearPrecio(precioPublico(aMoneda(licencia.precio, moneda, servicio.tipo_cambio_usd)), moneda)} ${moneda}`;
  return {
    id: licencia.personalizacion_id,
    dato: { etiqueta: ficha.licencia, valor: `+${monto}`, nota: ficha.licenciaNota },
  };
}

/**
 * Quién te lleva, de la empresa protagonista de la sede: la familia (Puerto Chale) con su nombre, sus datos y su
 * retrato, o el gremio (La Paz) con su foto y su relato. Sin «Conócenos» en la sede, `null` y la empresa va al final.
 */
function quienDe(empresaSlug: string, { lang, dict, sede }: Comun): VistaQuien | null {
  if (!sede || sede.empresaProtagonistaSlug !== empresaSlug) return null;
  const enlace = { href: hrefSede(lang, sede.slug, ANCLA_DE.conocenos), etiqueta: dict.sedeContenido.detalle.conoceHistoria };
  const empresa = getEmpresa(empresaSlug)?.nombre;
  if (sede.familia) {
    const { quien, retrato, fotos, apertura } = sede.familia;
    return { nombre: quien.nombre, empresa, detalles: quien.detalles, texto: apertura, retrato, fotos, enlace };
  }
  if (sede.conocenos) {
    const { foto, tripulacion, apertura } = sede.conocenos;
    return { nombre: empresa ?? sede.nombre, detalles: [], texto: apertura, retrato: foto, fotos: tripulacion.fotos, enlace };
  }
  return null;
}

/** El renglón del `h1`: el propio del producto o, sin él, el lugar («La Paz, Baja California Sur»). */
function encabezadoDe(propio: string | undefined, sede: SedeContenido | undefined): string | undefined {
  return propio ?? (sede ? `${sede.nombre}, Baja California Sur` : undefined);
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
  // Lo que más cambia la expectativa (el equipo, la licencia) va aquí y no solo en las preguntas (PFD, 2026-11-17).
  const equipo = equipoDeServicio(clave, lang);
  const licencia = licenciaDe(servicio, entrada);
  const ficha: DatoFicha[] = [
    ...(vista?.horario ? [{ etiqueta: detalle.ficha.salida, valor: vista.horario }] : []),
    ...(servicio?.duracion ? [{ etiqueta: detalle.ficha.duracion, valor: servicio.duracion }] : []),
    ...(servicio?.capacidad_maxima
      ? [{ etiqueta: detalle.ficha.personas, valor: detalle.ficha.hasta.replace('{n}', String(servicio.capacidad_maxima)) }]
      : []),
    ...(equipo ? [{ etiqueta: detalle.ficha.equipo, valor: equipo.valor, nota: equipo.nota }] : []),
    ...(licencia ? [licencia.dato] : []),
    ...(servicio?.punto_salida
      ? [{
          etiqueta: detalle.ficha.salesDe,
          valor: servicio.punto_salida,
          ...(() => {
            const href = enlaceAlMapa(servicio.punto_salida, sede?.nombre);
            return href ? { enlace: { href, etiqueta: detalle.verMapa } } : {};
          })(),
        }]
      : []),
  ];
  const alMar = tipo === 'pesca' || tipo === 'paseo';
  // La propina va con lo que no incluye, dicha antes de pagar: nadie la descubre en la panga.
  const noIncluye = alMar ? [...propia.noIncluye, detalle.propina] : propia.noIncluye;
  // El cupo máximo ya va en la ficha: el bloque de compra se queda con quién, cuántos cubre el precio y cómo pagas.
  const datos = [
    { etiqueta: detalle.etiquetaOpera, valor: nombreEmpresa },
    ...(servicio && porGrupo ? [{ etiqueta: detalle.etiquetaIncluye, valor: detalle.personas.replace('{n}', String(servicio.personas_incluidas)) }] : []),
    ...(servicio ? [datosDePago(servicio.permite_anticipo, servicio.porcentaje_anticipo, entrada)] : []),
  ];
  const puedeReservar = servicio !== null || pesca || traslado;

  return {
    titulo,
    // El traslado no es de una sede: sin renglón.
    // El encabezado propio puede decir la duración del backoffice; sin ella, el genérico de la sede.
    encabezado: traslado ? undefined : encabezadoDe(conCatalogo(seoDeServicio(empresaSlug, slug)?.encabezado[lang], servicio ? [servicio, ...(entrada.otros.servicios ?? [])] : entrada.otros.servicios, lang) || undefined, sede),
    lead,
    color: servicio ? colorDeServicio(servicio) : colorDeServicio({ tipo_servicio: tipo }),
    palabra: palabraDeServicio(tipo, lang),
    foto: imagenDeCatalogo(clave, lang),
    fotos: imagenesDeCatalogo(clave, lang),
    galeria: galeriaDeCatalogo(clave, lang),
    linea: textos.opera.replace('{empresa}', nombreEmpresa),
    tituloQueEs: detalle.queEs,
    ficha,
    especies: { titulo: detalle.sePesca, items: tipo === 'pesca' ? especiesDe(clave, entrada) : [] },
    reglas: {
      titulo: detalle.reglas.titulo,
      items: etiquetasDeReglas(reglasDeServicio(clave), detalle.reglas).map((texto) => ({ texto })),
    },
    incluye: { titulo: detalle.queIncluye, items: incluye, noIncluye },
    extras: { titulo: detalle.puedesAgregar, items: extrasDe(servicio ? [servicio] : [], entrada, new Set(licencia ? [licencia.id] : [])) },
    otros,
    // Los bloques escritos dicen duraciones y horarios del backoffice con marcas (`catalogo-en-texto`).
    bloques: conCatalogo(bloquesDeDetalle(clave, lang), servicio ? [servicio, ...(entrada.otros.servicios ?? [])] : entrada.otros.servicios, lang),
    preguntaIncluye: servicio && !traslado && !pesca && propia.incluye.length === 0 && tieneWhatsapp
      ? { etiqueta: textos.preguntaIncluye, href: whatsappHref(textos.whatsappMensaje.replace('{sede}', sede?.nombre ?? '')) }
      : null,
    compra: {
      precio: vista ? (vista.precio ?? 'ruta') : traslado ? 'ruta' : null,
      datos,
      nota: traslado
        ? dict.serviceDetail.transferInstructions
        : servicio && porGrupo ? notaDeExtra(servicio.personas_incluidas, servicio.precio_persona_extra, servicio.tipo_cambio_usd, servicio.capacidad_maxima, entrada) : undefined,
      condiciones: puedeReservar
        ? condicionesDe(traslado || tipo === 'transporte' ? 'traslado' : alMar ? 'mar' : 'otro', alMar, entrada)
        : null,
      href: puedeReservar
        ? hrefServicio(servicio ?? { slug, empresa_slug: empresaSlug, tipo_servicio: tipo }, lang, moneda, { origen: 'servicio', sede: sede?.slug })
        : null,
      etiquetaBoton: detalle.reservarServicio.replace('{nombre}', titulo),
    },
    quien: quienDe(empresaSlug, entrada),
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
    encabezado: encabezadoDe(entrada.sede ? seoDePaquete(entrada.sede.slug, paquete.slug)?.encabezado[lang] : undefined, entrada.sede),
    lead: paquete.descripcion,
    color: colorDePaquete(paquete),
    palabra: palabraDePaquete(paquete.noches, lang),
    foto: imagenDeCatalogo(clave, lang),
    fotos: imagenesDeCatalogo(clave, lang),
    galeria: galeriaDeCatalogo(clave, lang),
    linea: textos.opera.replace('{empresa}', nombresEmpresa.join(' · ')),
    tituloQueEs: detalle.queEsPaquete,
    ficha,
    especies: { titulo: detalle.sePesca, items: [] },
    reglas: { titulo: detalle.reglas.titulo, items: [] },
    incluye: { titulo: detalle.queIncluyePaquete, items: incluye, noIncluye: propia.noIncluye },
    extras: { titulo: detalle.puedesAgregar, items: extrasDe(servicios, entrada) },
    otros: [],
    bloques: conCatalogo(bloquesDeDetalle(clave, lang), servicios, lang),
    preguntaIncluye: null,
    compra: {
      precio: vista.precio,
      datos,
      nota: paquete.es_cruza_empresa
        ? detalle.cobroPorEmpresa
        : porGrupo ? notaDeExtra(paquete.personas_precio_base, paquete.precio_persona_extra, paquete.tipo_cambio_usd, undefined, entrada) : undefined,
      condiciones: condicionesDe(paquete.noches ? 'paquete-hotel' : 'paquete', salidasAlMar > 0, entrada),
      href: hrefPaquete(paquete, lang, moneda),
      etiquetaBoton: detalle.reservarServicio.replace('{nombre}', paquete.nombre),
    },
    quien: quienDe(paquete.empresa_lider_slug, entrada),
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
