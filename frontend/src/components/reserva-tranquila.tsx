import type { ReactNode } from 'react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappLogo } from '@phosphor-icons/react/ssr';
import { CifraContada } from '@/components/ui/cifra-contada';
import { botonClases } from '@/components/ui/variantes';
import { SectionShell, type Fondo } from '@/components/ui/section-shell';

type Textos = Dictionary['sedeContenido']['tranquilidad'];

/** El ejemplo de pago, calculado en la página con el servicio destacado. */
export type EjemploPago = { servicio: string; ahora: string; resto: string | null };

type Props = {
  id: string;
  textos: Textos;
  /** El `porcentaje_anticipo` de un servicio de la sede que lo permite; `null` = todos se pagan completos. */
  porcentaje: number | null;
  ejemplo: EjemploPago | null;
  /** Atención al cliente por WhatsApp: el número ya formateado y el enlace con el mensaje escrito. Sin número configurado, no hay bloque. */
  atencion: { numero: string; href: string } | null;
  fondo: Fondo;
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
 * al entrar. Una sola política para las cuatro empresas. Al final, el número de atención al cliente. El ejemplo de pago va aparte, a todo el ancho
 * bajo las tres cifras: dentro de la primera columna la dejaba más alta que las otras dos.
 *
 * Server Component (las cifras que cuentan son una isla cliente).
 */
export function ReservaTranquila({ id, textos, porcentaje, ejemplo, atencion, fondo }: Props) {
  return (
    <SectionShell id={id} fondo={fondo} titulo={textos.titulo}>
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
      {ejemplo && (
        <div className="mt-12 flex flex-col gap-x-12 gap-y-4 bg-white/10 px-6 py-6 lg:mt-16 lg:flex-row lg:items-center lg:px-10">
          <p className="texto-subtitulo lg:max-w-[22ch]">{textos.ejemploServicio.replace('{servicio}', ejemplo.servicio)}</p>
          <dl className="grid flex-1 gap-x-12 gap-y-4 sm:grid-cols-2">
            <div>
              <dt className="texto-cuerpo">{textos.hoyPagas}</dt>
              <dd className="text-xl font-bold tabular-nums">{ejemplo.ahora}</dd>
            </div>
            {ejemplo.resto && (
              <div>
                <dt className="texto-cuerpo">{textos.resto}</dt>
                <dd className="text-xl font-bold tabular-nums">{ejemplo.resto}</dd>
              </div>
            )}
          </dl>
        </div>
      )}
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
