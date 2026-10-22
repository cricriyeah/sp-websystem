import { FotoAleatoria } from '@/components/foto-aleatoria';
import { botonClases } from '@/components/ui/variantes';

type Props = {
  id: string;
  titulo: string;
  texto: string;
  pasos: { verbo: string; texto: string }[];
  cta: { href: string; etiqueta: string };
};

/**
 * Fotos del hub (decisión del dueño, 2026-10-22): una al azar en cada visita. Solo van en el hub, nunca en
 * las cortinas ni en las páginas de sede. Decorativas: los pasos dicen todo.
 */
const FOTOS = [
  'pez-en-el-anzuelo', 'cardon-junto-al-mar', 'cardones-contra-el-cielo', 'pescador-con-cana', 'roca-frente-al-mar',
  'brazos-abiertos-al-mar', 'caminata-en-la-sierra', 'salto-al-mar', 'cardones-al-atardecer', 'corriendo-a-las-olas',
  'pangas-en-la-playa', 'caminando-por-la-costa', 'cana-frente-al-mar', 'pesca-al-atardecer',
].map((nombre) => `/sunbajaexperience/fotos/${nombre}.webp`);

/**
 * Cómo funciona el sitio: un lugar que reúne a las empresas locales; cada una opera y cobra directo.
 * Una sola foto grande a la izquierda (fija al bajar en escritorio) y a la derecha el título, el párrafo y
 * los tres pasos en lista, cada uno con su verbo grande y su frase completa en texto de lectura; cierra con
 * «Elige tu destino», que sube a las sedes. En el teléfono la foto va arriba y los pasos debajo.
 *
 * Server Component.
 */
export function HubComoFunciona({ id, titulo, texto, pasos, cta }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-[calc(var(--nav-alto)+16px)] bg-superficie py-16 sm:py-20 lg:py-28">
      <div className="mx-auto grid max-w-[1440px] items-start gap-10 px-4 sm:px-6 lg:grid-cols-12 lg:gap-12 lg:px-12">
        <div className="relative aspect-[4/3] overflow-hidden bg-tinta lg:sticky lg:top-[calc(var(--nav-alto)+1.5rem)] lg:col-span-6 lg:aspect-[4/5]">
          <FotoAleatoria fotos={FOTOS} sizes="(min-width: 1024px) 50vw, 100vw" />
        </div>

        <div className="lg:col-span-5 lg:col-start-8">
          <h2 id={`${id}-titulo`} className="rev max-w-[20ch] texto-seccion text-foreground">{titulo}</h2>
          <p className="rev mt-4 max-w-[52ch] texto-cuerpo text-foreground">{texto}</p>
          <ol className="mt-12 flex flex-col gap-10 lg:mt-16 lg:gap-14">
            {pasos.map((paso) => (
              <li key={paso.verbo} className="rev">
                <h3 className="texto-grande text-foreground">{paso.verbo}</h3>
                <p className="mt-3 max-w-[44ch] text-lg leading-snug text-foreground">{paso.texto}</p>
              </li>
            ))}
          </ol>
          <a href={cta.href} className={`rev mt-12 max-sm:w-full max-sm:justify-center lg:mt-16 ${botonClases({ variante: 'campana' })}`}>
            {cta.etiqueta}
            <span aria-hidden="true">→</span>
          </a>
        </div>
      </div>
    </section>
  );
}
