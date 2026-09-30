type Pilar = { titulo: string; texto: string };

type HubPorQueProps = {
  headline: string;
  pilares: Pilar[];
};

export function HubPorQue({ headline, pilares }: HubPorQueProps) {
  return (
    <section id="nosotros" className="scroll-mt-28 mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
      <h2 className="max-w-[20ch] text-3xl leading-[1.05] text-foreground sm:text-4xl">{headline}</h2>
      <div className="mt-10 grid gap-8 sm:grid-cols-3">
        {pilares.map((pilar) => (
          <div key={pilar.titulo} className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-foreground">{pilar.titulo}</h3>
            <p className="text-sm leading-relaxed text-muted">{pilar.texto}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
