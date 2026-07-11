export const metadata = {
  title: "Terms of Service — TrueBrief",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">{title}</h2>
      <div className="text-sm text-[var(--color-text-secondary)] leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function TermsPage() {
  return (
    <div className="bg-[var(--color-surface)]">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24">
        <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">Terms of Service</h1>
        <p className="text-xs text-[var(--color-text-muted)] mb-10">Last updated: July 10, 2026</p>

        <Section title="1. The service">
          <p>
            TrueBrief monitors news topics you choose, filters out material you have already
            seen, and delivers summaries of new developments (&quot;briefs&quot;) with links to the
            original sources. Paid plans additionally include programmatic access to your
            data via the developer API.
          </p>
        </Section>

        <Section title="2. Accounts">
          <p>
            You need an account to use TrueBrief. You are responsible for activity under
            your account and for keeping your credentials and API keys secret. You must be
            at least 16 years old.
          </p>
        </Section>

        <Section title="3. Plans, billing, and cancellation">
          <p>
            Paid subscriptions (Pro, Power) are billed monthly through our payment provider,
            Paddle, which acts as merchant of record. You can cancel at any time from the
            billing portal; access continues until the end of the paid period. Plan limits
            (topics, scan frequency, API calls) are described on the pricing page and may be
            enforced automatically.
          </p>
        </Section>

        <Section title="4. Acceptable use">
          <p>
            Don&apos;t abuse the service: no attempts to circumvent plan limits, probe or
            disrupt the infrastructure, resell raw output without an enterprise agreement, or
            use the service for unlawful purposes. API keys may be revoked and accounts
            suspended for abuse.
          </p>
        </Section>

        <Section title="5. Content and sources">
          <p>
            Briefs are automatically generated summaries of publicly available reporting.
            Each fact links to its source; the underlying articles belong to their
            publishers. TrueBrief summarises and attributes — it does not republish full
            articles.
          </p>
        </Section>

        <Section title="6. No warranty">
          <p>
            TrueBrief is provided &quot;as is&quot;. News monitoring is inherently imperfect:
            summaries can contain errors, sources can be wrong, and coverage can miss
            developments. Do not rely on TrueBrief as your sole source for decisions with
            legal, financial, medical, or safety consequences.
          </p>
        </Section>

        <Section title="7. Limitation of liability">
          <p>
            To the maximum extent permitted by law, TrueBrief&apos;s total liability for any
            claim arising out of the service is limited to the amount you paid us in the
            three months before the claim arose.
          </p>
        </Section>

        <Section title="8. Termination">
          <p>
            You can delete your account at any time from Settings, which permanently removes
            your data. We may suspend or terminate accounts that violate these terms.
          </p>
        </Section>

        <Section title="9. Changes">
          <p>
            We may update these terms as the product evolves. Material changes will be
            announced in the app or by email. Continuing to use the service after a change
            means you accept the new terms.
          </p>
        </Section>

        <Section title="10. Contact">
          <p>
            Questions about these terms: <a href="mailto:kfirmessika@gmail.com" className="text-[var(--color-brand)]">kfirmessika@gmail.com</a>
          </p>
        </Section>
      </div>
    </div>
  );
}
