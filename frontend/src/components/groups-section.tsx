import { UsersThree } from '@phosphor-icons/react/ssr';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { WhatsappInline } from '@/components/whatsapp-inline';

type GroupsSectionProps = {
  nav: Dictionary['nav'];
  groups: Dictionary['groups'];
};

/**
 * Grupos de mas de 6. El checkout tiene tope de 6 (la panga mas grande), asi que
 * sin esto una familia de 9 se topa con pared y se va. Se resuelve por WhatsApp:
 * coordinar varias pangas es trabajo de la vendedora, no de un formulario.
 */
export function GroupsSection({ nav, groups }: GroupsSectionProps) {
  return (
    <section className="bg-background pb-24 lg:pb-32">
      <div className="mx-auto max-w-6xl px-6 sm:px-8 lg:px-12">
        <div className="flex flex-col gap-6 rounded-3xl border border-border bg-surface p-8 sm:p-10 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="flex items-center gap-3 text-xl font-medium tracking-tight text-foreground sm:text-2xl">
              <UsersThree size={24} className="shrink-0 text-accent" />
              {groups.headline}
            </h2>
            <p className="mt-3 max-w-[60ch] text-sm leading-relaxed text-muted">{groups.body}</p>
          </div>
          <WhatsappInline nav={nav} label={groups.cta} className="shrink-0" />
        </div>
      </div>
    </section>
  );
}
