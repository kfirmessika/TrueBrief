export const metadata = {
  title: "Privacy Policy — TrueBrief",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">{title}</h2>
      <div className="text-sm text-[var(--color-text-secondary)] leading-relaxed space-y-3">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <div className="bg-[var(--color-surface)]">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24">
        <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">Privacy Policy</h1>
        <p className="text-xs text-[var(--color-text-muted)] mb-10">Last updated: July 10, 2026</p>

        <Section title="What we collect">
          <p>
            <strong className="text-[var(--color-text)]">Account data</strong> — your name and
            email, handled by our authentication provider (Clerk).
          </p>
          <p>
            <strong className="text-[var(--color-text)]">Product data</strong> — the topics you
            create, the briefs we generate for you, your reading state (what you&apos;ve seen),
            and your notification/digest preferences.
          </p>
          <p>
            <strong className="text-[var(--color-text)]">Billing data</strong> — payments are
            processed by Paddle as merchant of record. We never see or store your card details;
            we store only your subscription tier and status.
          </p>
          <p>
            <strong className="text-[var(--color-text)]">Technical data</strong> — standard
            server logs (IP, timestamps, endpoints) used for security and debugging, and API
            usage counts for quota enforcement.
          </p>
        </Section>

        <Section title="What we do with it">
          <p>
            We use your data to run the product: monitor your topics, generate briefs, send
            digests you opted into, enforce plan limits, and improve reliability. Topic text is
            sent to third-party AI providers (e.g. Google, Groq) to generate summaries — never
            your name, email, or billing details alongside it.
          </p>
        </Section>

        <Section title="What we don't do">
          <p>
            We don&apos;t sell your data. We don&apos;t share your topics or briefs with other
            users (free-plan topic <em>queries</em> may be pooled anonymously so shared scans
            stay efficient; Pro/Power topics are private). We don&apos;t send marketing email
            you didn&apos;t ask for.
          </p>
        </Section>

        <Section title="Where it lives">
          <p>
            Data is stored with our infrastructure providers: Supabase (database), Railway
            (application hosting), Clerk (authentication), and Paddle (billing). Each processes
            data under their own security and compliance programs.
          </p>
        </Section>

        <Section title="Your controls">
          <p>
            You can delete individual topics at any time, revoke API keys, disable digests and
            notifications, and delete your entire account from Settings — account deletion
            permanently removes your topics, briefs, and reading history.
          </p>
        </Section>

        <Section title="Data retention">
          <p>
            We keep your data while your account exists. Deleted accounts are purged from the
            live database immediately; residual copies in encrypted backups expire on the
            backup rotation schedule.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Privacy questions or data requests: <a href="mailto:kfirmessika@gmail.com" className="text-[var(--color-brand)]">kfirmessika@gmail.com</a>
          </p>
        </Section>
      </div>
    </div>
  );
}
