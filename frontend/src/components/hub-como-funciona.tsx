import Image from 'next/image';
import { cn } from '@/components/ui/cn';

type Props = {
  id: string;
  titulo: string;
  texto: string;
  pasos: { verbo: string; texto: string }[];
};

/**
 * Fotos de los tres pasos. DE RELLENO (decisión del dueño, 2026-10-19: usar lo que ya hay hasta subir
 * las reales). Decorativas: el verbo y el texto de cada paso dicen todo.
 */
const FOTOS = [
  '/photos/capitan-cabrilla-bahia.webp',
  '/photos/pareja-dorados.webp',
  '/photos/cana-doblada-dorado.webp',
];

// El orden lo da el tamaño: cada foto es más grande que la anterior. Clases completas para Tailwind.
const TAMANOS = [
  'md:col-span-3 md:h-[clamp(20rem,46svh,28.75rem)]',
  'md:col-span-4 md:h-[clamp(25rem,58svh,36rem)]',
  'md:col-span-5 md:h-[clamp(30rem,72svh,45rem)]',
];

/**
 * Cómo funciona el sitio (F10): un lugar que reúne a las empresas locales; cada una opera y cobra
 * directo. Tres fotos que crecen de tamaño, cada una con su verbo gigante y su frase. En móvil van
 * una debajo de otra.
 *
 * Server Component.
 */
export function HubComoFunciona({ id, titulo, texto, pasos }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-[calc(var(--nav-alto)+16px)] bg-superficie py-16 sm:py-20 lg:py-28">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-12">
        <h2 id={`${id}-titulo`} className="max-w-[24ch] texto-seccion text-foreground">{titulo}</h2>
        <p className="mt-4 max-w-[60ch] texto-cuerpo text-foreground">{texto}</p>
        <ol className="mt-10 grid gap-2 md:grid-cols-12 md:items-end">
          {pasos.map((paso, i) => (
            <li
              key={paso.verbo}
              className={cn('group relative h-[clamp(20rem,56svh,28.75rem)] overflow-hidden bg-tinta text-hero-ink', TAMANOS[i])}
            >
              <Image
                src={FOTOS[i] ?? FOTOS[0]}
                alt=""
                fill
                sizes="(min-width: 768px) 42vw, 100vw"
                loading="lazy"
                className="object-cover transition-transform duration-[900ms] ease-[var(--curva-estandar)] motion-reduce:transition-none [@media(hover:hover)]:group-hover:scale-[1.04]"
              />
              <div aria-hidden="true" className="absolute inset-0" style={{ background: 'var(--scrim-hero)' }} />
              <div className="absolute inset-x-0 bottom-0 flex flex-col gap-3 p-5 sm:p-6">
                <h3 className="texto-grande text-balance">{paso.verbo}</h3>
                <p className="max-w-[34ch] texto-pequeno leading-snug">{paso.texto}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
