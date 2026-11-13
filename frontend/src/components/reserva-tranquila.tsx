import type { ReactNode } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappLogo } from '@phosphor-icons/react/ssr';
import { CifraContada } from '@/components/ui/cifra-contada';
import { botonClases } from '@/components/ui/variantes';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';
import type { LogoLargo } from '@/content/empresas-marca';

type Textos = Dictionary['sedeContenido']['tranquilidad'];

type Props = {
  id: string;
  textos: Textos;
  /** El `porcentaje_anticipo` de un servicio de la sede que lo permite; `null` = todos se pagan completos. */
  porcentaje: number | null;
  /** Atención al cliente por WhatsApp: el número ya formateado y el enlace con el mensaje escrito. Sin número configurado, no hay bloque. */
  atencion: { numero: string; href: string } | null;
  fondo: Fondo;
  /**
   * La empresa que opera la sede: su isotipo va como sello pegado al título y de su alto (estas reglas las respalda
   * ella); en la banda tinta, con el círculo blanco por fuera si hay isotipo transparente (`sinFondo`).
   */
  sello?: { isotipo: string; sinFondo?: string; empresa: string; largo?: LogoLargo };
  /** La ilustración de la empresa detrás de las cifras (`MarcaEmpresa.ilustracionFondo`); con ella no va el sello. */
  ilustracion?: string;
};

function Cifra({ cifra, titulo, children }: { cifra: string; titulo: string; children: ReactNode }) {
  return (
    <li className="flex flex-col gap-3">
      <CifraContada cifra={cifra} className="texto-grande block text-cafe-claro tabular-nums" />
      <h3 className="texto-subtitulo">{titulo}</h3>
      <div className="max-w-[34ch] texto-cuerpo">{children}</div>
    </li>
  );
}

/**
 * Pago, clima y cambio de fecha como tres cifras grandes en la banda negra (F10), que cuentan desde cero
 * al entrar. Una sola política para las cuatro empresas. Al final, el número de atención al cliente. Con `sello`, el
 * isotipo de la empresa que opera la sede va pegado al título, como sello de que respalda esas reglas (un solo logo
 * en toda la banda: también cubre el bloque de atención). Si la empresa tiene `ilustracion`, su logo va de fondo,
 * grande y tenue detrás de las cifras, y no hay sello junto al título (pedido del dueño, 2026-10-30).
 *
 * Server Component (las cifras que cuentan son una isla cliente).
 */
export function ReservaTranquila({ id, textos, porcentaje, atencion, fondo, sello, ilustracion }: Props) {
  return (
    <SectionShell
      id={id}
      fondo={fondo}
      titulo={textos.titulo}
      sello={!ilustracion && sello ? { isotipo: sello.isotipo, sinFondo: sello.sinFondo, alt: sello.empresa, largo: sello.largo } : undefined}
      ilustracion={ilustracion}
    >
      <ul className="mt-12 grid gap-12 md:grid-cols-3 md:gap-8 lg:mt-16">
        <Cifra cifra={porcentaje === null ? textos.cifraTotal : `${porcentaje} %`} titulo={textos.pagoTitulo}>
          <p>{porcentaje === null ? textos.pagoTextoTotal : textos.pagoTexto.replace('{porcentaje}', String(porcentaje))}</p>
        </Cifra>
        <Cifra cifra={textos.cifraFecha} titulo={textos.fechaTitulo}>
          <p>{textos.fechaTexto}</p>
        </Cifra>
        <Cifra cifra={textos.cifraTotal} titulo={textos.climaTitulo}>
          <p>{textos.climaTexto}</p>
        </Cifra>
      </ul>
      {atencion && (
        <div className="mt-12 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between lg:mt-16">
          <div>
            <h3 className="texto-subtitulo">{textos.atencionTitulo}</h3>
            <p className="mt-2 max-w-[48ch] texto-cuerpo">{textos.atencionTexto}</p>
          </div>
          <a
            href={atencion.href}
            target="_blank"
            rel="noopener"
            className={botonClases({ variante: 'campana-claro' })}
          >
            <WhatsappLogo size={20} weight="fill" aria-hidden="true" />
            {atencion.numero}
          </a>
        </div>
      )}
    </SectionShell>
  );
}
