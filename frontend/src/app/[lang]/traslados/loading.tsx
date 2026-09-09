import { Skeleton } from '@/components/skeleton';

export default function LoadingTraslados() {
  return (
    <div className="min-h-dvh bg-background">
      <div className="border-b border-border px-6 py-5 sm:px-8 lg:px-12">
        <Skeleton className="h-6 w-32" />
      </div>

      <div className="mx-auto max-w-6xl px-6 pt-6 sm:px-8 lg:px-12">
        <Skeleton className="h-4 w-24" />
      </div>

      <main className="mx-auto grid max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex flex-col gap-6">
          <section className="border border-border bg-surface p-6 sm:p-8">
            <Skeleton className="h-5 w-48" />
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          </section>

          <section className="border border-border bg-surface p-6 sm:p-8">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="mt-4 h-12 w-full" />
          </section>

          <section className="border border-border bg-surface p-6 sm:p-8">
            <Skeleton className="h-5 w-36" />
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          </section>
        </div>

        <section className="border border-border bg-surface p-6 shadow-[0_18px_45px_rgba(11,36,32,0.16)] sm:p-8">
          <Skeleton className="h-5 w-28" />
          <div className="mt-6 flex flex-col gap-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
          </div>
          <Skeleton className="mt-6 h-px w-full" />
          <Skeleton className="mt-6 h-7 w-32" />
          <Skeleton className="mt-6 h-12 w-full rounded-full" />
        </section>
      </main>
    </div>
  );
}
