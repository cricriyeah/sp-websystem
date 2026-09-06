export default function CatalogoLoading() {
  return (
    <div className="min-h-dvh bg-background">
      <div className="mx-auto max-w-6xl px-6 pt-[calc(3rem_+_var(--nav-alto))] pb-16 sm:px-8 lg:px-12">
        <div className="h-10 w-64 animate-pulse rounded-lg bg-muted/20" />
        <div className="mt-3 h-5 w-96 animate-pulse rounded-md bg-muted/15" />

        <div className="mt-8 h-12 w-48 animate-pulse rounded-xl bg-muted/20" />

        <div className="mt-12 grid gap-8 md:grid-cols-2">
          <div className="h-96 animate-pulse rounded-2xl border border-border bg-card/60 p-8" />
          <div className="h-96 animate-pulse rounded-2xl border border-border bg-card/60 p-8" />
        </div>
      </div>
    </div>
  );
}
