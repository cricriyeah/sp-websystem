import Link from 'next/link';
import { MapPin, Anchor } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type SiteFooterProps = {
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
};

export function SiteFooter({ footer, nav, bookLabel }: SiteFooterProps) {
  return (
    <footer id="contacto" className="scroll-mt-20 bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-3xl leading-[1.15] font-medium tracking-tight text-foreground sm:text-4xl">
              {footer.headline}
            </h2>

            <div className="mt-8 flex flex-col gap-6 sm:flex-row sm:gap-14">
              <div className="flex gap-3">
                <MapPin size={20} className="mt-0.5 shrink-0 text-accent" />
                <div>
                  <p className="text-sm text-muted">{footer.addressLabel}</p>
                  <p className="mt-1 text-base text-foreground">{footer.address}</p>
                  <p className="text-base text-foreground">{footer.city}</p>
                </div>
              </div>

              <div className="flex gap-3">
                <Anchor size={20} className="mt-0.5 shrink-0 text-accent" />
                <div>
                  <p className="text-sm text-muted">{footer.hoursLabel}</p>
                  <p className="mt-1 text-base text-foreground">{footer.hours}</p>
                </div>
              </div>
            </div>
          </div>

          <Link
            href="#inicio"
            className="inline-flex shrink-0 items-center justify-center rounded-full bg-accent px-8 py-4 text-sm font-medium text-accent-foreground transition-transform active:scale-[0.98]"
          >
            {bookLabel}
          </Link>
        </div>

        <p className="mt-16 border-t border-border pt-8 text-sm text-muted">
          {new Date().getFullYear()} {nav.brandMain} {nav.brandAccent}. {footer.rights}
        </p>
      </div>
    </footer>
  );
}
