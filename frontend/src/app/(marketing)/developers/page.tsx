import Link from "next/link";
import { ArrowRight, Key, Zap, Shield } from "lucide-react";

export const metadata = {
  title: "Developer API — TrueBrief",
  description: "Programmatic access to TrueBrief's verified, deduplicated fact stream.",
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.truebrief.app";

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-overlay)] p-4 text-[13px] leading-relaxed text-[var(--color-text-secondary)] overflow-x-auto">
      <code>{children}</code>
    </pre>
  );
}

function Endpoint({ method, path, desc }: { method: string; path: string; desc: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 py-3 border-b border-[var(--color-border)] last:border-b-0">
      <span className="inline-flex w-fit items-center rounded-md px-2 py-0.5 text-[11px] font-bold text-white shrink-0"
        style={{ background: 'oklch(0.55 0.22 264)' }}>
        {method}
      </span>
      <code className="text-[13px] font-semibold text-[var(--color-text)] shrink-0">{path}</code>
      <span className="text-[13px] text-[var(--color-text-secondary)] sm:ml-auto">{desc}</span>
    </div>
  );
}

export default function DevelopersPage() {
  return (
    <div className="bg-[var(--color-surface)]">
      {/* Hero */}
      <section className="pt-20 pb-12 md:pt-28">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-xs font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">
            Developer API
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[var(--color-text)] mb-5">
            The fact stream,<br />in your product.
          </h1>
          <p className="text-lg text-[var(--color-text-secondary)] leading-relaxed max-w-xl mb-8">
            Every fact TrueBrief stores has been deduplicated against history, scored for
            signal, and linked to its source. Pull that stream straight into your own
            dashboards, agents, and workflows.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-all active:scale-[0.98] hover:opacity-90"
              style={{ background: 'oklch(0.55 0.22 264)' }}
            >
              Get an API key <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#quickstart"
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-5 py-2.5 text-sm font-semibold text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-surface-overlay)]"
            >
              Quickstart
            </a>
          </div>
        </div>
      </section>

      {/* Value props */}
      <section className="pb-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 grid sm:grid-cols-3 gap-4">
          {[
            { icon: Zap, title: "Signal, not articles", desc: "Facts arrive deduplicated and signal-scored — no feed of 40 near-identical headlines." },
            { icon: Shield, title: "Source-linked", desc: "Every fact carries its source URL and domain, ready for citation." },
            { icon: Key, title: "Simple auth", desc: "One Bearer key. Create and revoke keys from your settings page." },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5">
              <f.icon className="h-4 w-4 mb-3" style={{ color: 'oklch(0.55 0.22 264)' }} />
              <h3 className="text-sm font-semibold text-[var(--color-text)] mb-1.5">{f.title}</h3>
              <p className="text-[13px] text-[var(--color-text-secondary)] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Quickstart */}
      <section id="quickstart" className="py-16 bg-[var(--color-surface-raised)] border-y border-[var(--color-border)]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-[var(--color-text)] mb-2">Quickstart</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-8">
            API access is included with Pro and Power plans. Create a key in{" "}
            <Link href="/settings" className="text-[var(--color-brand)] font-medium">Settings → Developer API</Link>,
            then:
          </p>

          <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">1 · List your monitored topics</h3>
          <CodeBlock>{`curl ${API_BASE}/v1/topics \\
  -H "Authorization: Bearer tb_live_YOUR_KEY"`}</CodeBlock>

          <h3 className="text-sm font-semibold text-[var(--color-text)] mt-8 mb-3">2 · Pull the fact stream for a topic</h3>
          <CodeBlock>{`curl "${API_BASE}/v1/topics/TOPIC_ID/facts?days=7&limit=50" \\
  -H "Authorization: Bearer tb_live_YOUR_KEY"`}</CodeBlock>

          <h3 className="text-sm font-semibold text-[var(--color-text)] mt-8 mb-3">Example response</h3>
          <CodeBlock>{`{
  "topic_id": "…",
  "days": 7,
  "facts": [
    {
      "id": "…",
      "text": "Parliament votes to conditionally endorse the ceasefire terms.",
      "source_url": "https://www.reuters.com/…",
      "source_domain": "reuters.com",
      "first_seen_at": "2026-07-09T14:02:11Z",
      "event_class": "STATE_CHANGE",
      "signal_score": 9,
      "signal_class": "STATE_CHANGE"
    }
  ]
}`}</CodeBlock>
        </div>
      </section>

      {/* Endpoints */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-[var(--color-text)] mb-6">Endpoints</h2>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-5 py-2">
            <Endpoint method="GET" path="/v1/topics" desc="Topics you monitor" />
            <Endpoint method="GET" path="/v1/topics/{id}/facts" desc="Recent verified facts (days, limit params)" />
            <Endpoint method="GET" path="/v1/topics/{id}/history" desc="Full date-grouped timeline" />
            <Endpoint method="GET" path="/v1/usage" desc="Today's usage vs your quota (free to call)" />
          </div>

          <h3 className="text-sm font-semibold text-[var(--color-text)] mt-10 mb-3">Authentication</h3>
          <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mb-4">
            Pass your key as <code className="text-[13px] bg-[var(--color-surface-overlay)] px-1.5 py-0.5 rounded">Authorization: Bearer tb_live_…</code>{" "}
            or <code className="text-[13px] bg-[var(--color-surface-overlay)] px-1.5 py-0.5 rounded">X-API-Key</code>.
            Keys are shown once at creation and can be revoked at any time.
          </p>

          <h3 className="text-sm font-semibold text-[var(--color-text)] mt-8 mb-3">Rate limits</h3>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left">
                  <th className="px-5 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">Plan</th>
                  <th className="px-5 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">API calls / day</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="px-5 py-3 font-medium text-[var(--color-text)]">Pro</td>
                  <td className="px-5 py-3">500</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="px-5 py-3 font-medium text-[var(--color-text)]">Power</td>
                  <td className="px-5 py-3">5,000</td>
                </tr>
                <tr>
                  <td className="px-5 py-3 font-medium text-[var(--color-text)]">Enterprise</td>
                  <td className="px-5 py-3">Custom — <a href="mailto:kfirmessika@gmail.com?subject=TrueBrief%20Enterprise%20API" className="text-[var(--color-brand)] font-medium">talk to us</a></td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-[13px] text-[var(--color-text-muted)] mt-6 leading-relaxed">
            Over quota returns <code>429</code>; free-plan keys return <code>402</code>. Quotas are per account, not per key.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 border-t border-[var(--color-border)] bg-[var(--color-surface-raised)]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-bold text-[var(--color-text)] mb-3">Build on the fact stream</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-7 max-w-md mx-auto">
            Start on Pro, upgrade when you need volume, or talk to us about enterprise feeds and custom topics.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-white shadow-md transition-all active:scale-[0.98] hover:opacity-90"
            style={{ background: 'oklch(0.55 0.22 264)' }}
          >
            Get started <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
