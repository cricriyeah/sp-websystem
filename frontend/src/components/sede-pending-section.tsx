export function SedePendingSection({ id, title, body }: { id: string; title: string; body: string }) {
  return <section id={id} className="scroll-mt-28 mx-auto max-w-6xl border-t border-border px-6 py-12 sm:px-8 lg:px-12">
    <h2 className="text-3xl sm:text-4xl">{title}</h2>
    <p className="mt-4 max-w-2xl text-muted">{body}</p>
  </section>;
}
