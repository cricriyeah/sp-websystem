import type { ReactNode } from 'react';
import { Boat } from '@phosphor-icons/react/ssr';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Seccion } from '@/lib/secciones-sede';
import { ANCLA_DE } from '@/lib/secciones-sede';
import { hrefSede } from '@/lib/routes';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { TarjetaProducto, type VistaProducto } from '@/components/tarjeta-producto';
import { vistaDePaquete, vistaDeServicio } from '@/components/vistas-catalogo';
import { AvisoEstado } from '@/components/ui/aviso-estado';
import { FilaArrastrable } from '@/components/ui/fila-arrastrable';
import { CLASE_FONDO, SectionShell, type Fondo } from '@/components/ui/section-shell';
import { botonClases } from '@/components/ui/variantes';

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
};

type Elemento = { vista: VistaProducto; destacada: boolean };

/**
 * «Qué puedes reservar» (F10): los servicios y paquetes de la sede en una sola fila que se arrastra,
 * cada uno con su botón «Reservar →». Los paquetes van primero y el destacado de la sede abre la
 * fila. Proyecta en servidor la respuesta de la API a lo mínimo que pinta la tarjeta. Con el catálogo
 * caído o vacío pinta su estado, nunca «pronto».
 *
 * Server Component.
 */
export function QuePuedesReservar({ lang, moneda, sede, servicios, paquetes, estado, destacadas, textos, fondo }: Props) {
  const contacto = tieneWhatsapp ? whatsappHref(textos.whatsappMensaje.replace('{sede}', sede.nombre)) : null;
  const shell = (contenido: ReactNode) => (
    <SectionShell id={ANCLA_DE.reservar} fondo={fondo} titulo={textos.titulo}>
      {contenido}
    </SectionShell>
  );

  if (estado === 'catalogo_caido') {
    return shell(
      <AvisoEstado tono="error" className="mt-8">
        <p className="font-semibold">{textos.caido}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <a href={hrefSede(lang, sede.slug, ANCLA_DE.reservar)} className={botonClases({ variante: 'campana' })}>{textos.reintentar}</a>
          {contacto && <a href={contacto} target="_blank" rel="noopener noreferrer" className={botonClases({ variante: 'campana' })}>{textos.whatsapp}</a>}
        </div>
      </AvisoEstado>,
    );
  }

  if (estado === 'vacio') {
    return shell(
      <div className="mt-8 flex flex-col items-start gap-4 bg-cafe-bruma p-6">
        <Boat size={32} aria-hidden="true" />
        <p className="texto-cuerpo">{textos.vacio}</p>
        {contacto && <a href={contacto} target="_blank" rel="noopener noreferrer" className={botonClases({ variante: 'campana' })}>{textos.whatsapp}</a>}
      </div>,
    );
  }

  const primera = destacadas[0];
  const elementos: Elemento[] = [
    ...(paquetes ?? []).map((p) => ({
      vista: vistaDePaquete(p, lang, moneda),
      destacada: primera?.tipo === 'paquete' && primera.slug === p.slug,
    })),
    ...(servicios ?? []).map((s) => ({
      vista: vistaDeServicio(s, lang, moneda, sede.slug),
      destacada: primera?.tipo === 'servicio' && primera.slug === s.slug && (!primera.empresaSlug || primera.empresaSlug === s.empresa_slug),
    })),
  ].sort((a, b) => Number(b.destacada) - Number(a.destacada));
  const textosTarjeta = { ...textos, reservarAria: textos.verYReservarAria };
  let fotosPintadas = 0;

  // La fila lleva su propio encabezado (título y flechas), por eso no usa el contenedor de `SectionShell`.
  return (
    <section
      id={ANCLA_DE.reservar}
      aria-labelledby={`${ANCLA_DE.reservar}-titulo`}
      className={`scroll-mt-[calc(var(--nav-alto)+16px)] ${CLASE_FONDO[fondo]} py-16 sm:py-20 lg:py-28`}
    >
      <FilaArrastrable
        cabeza={<h2 id={`${ANCLA_DE.reservar}-titulo`} className="rev texto-seccion">{textos.titulo}</h2>}
        etiqueta={textos.carril.replace('{sede}', sede.nombre)}
        textos={{ anterior: textos.flechaAnterior, siguiente: textos.flechaSiguiente }}
      >
        {elementos.map(({ vista }) => (
          <TarjetaProducto key={vista.clave} vista={vista} textos={textosTarjeta} prioridad={Boolean(vista.foto) && fotosPintadas++ < 2} />
        ))}
      </FilaArrastrable>
    </section>
  );
}
