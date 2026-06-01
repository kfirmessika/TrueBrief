import Link from "next/link";
import { ArrowRight, Zap, CheckCircle, Filter, BookOpen, Clock, Globe, Lock } from "lucide-react";

// ── Product preview shown in hero ──────────────────────────────────────────

function BriefPreviewCard() {
  return (
    <div className="relative mx-auto max-w-md text-left">
      {/* Glow behind the card */}
      <div className="absolute -inset-4 rounded-3xl blur-2xl opacity-30 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, oklch(0.55 0.22 264 / 0.4), transparent 70%)' }} />

      <div className="relative rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-xl overflow-hidden">
        {/* Card header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--color-border)] bg-[var(--color-surface-overlay)]">
          <div className="flex items-center gap-2.5">
            <div className="h-2 w-2 rounded-full bg-[var(--color-success)] animate-pulse" />
            <span className="text-xs font-semibold text-[var(--color-text)] tracking-wide">NVIDIA Earnings</span>
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">2 min ago</span>
        </div>

        {/* New facts */}
        <div className="px-5 pt-4 pb-2">
          <p className="text-[10px] font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">
            3 new facts since your last read
          </p>
          <ul className="space-y-3">
            {[
              'Revenue beat expectations by 12% — $22.1B vs. $19.6B estimated',
              'Blackwell GPU architecture launches ahead of schedule',
              'Data center now represents 87% of total revenue',
            ].map((fact, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="h-1.5 w-1.5 rounded-full bg-[var(--color-brand)] mt-2 shrink-0" />
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{fact}</p>
              </li>
            ))}
          </ul>
        </div>

        {/* Card footer */}
        <div className="flex items-center justify-between px-5 py-3 mt-2 border-t border-[var(--color-border)] bg-[var(--color-surface-overlay)]">
          <span className="text-[11px] text-[var(--color-text-muted)]">47 articles scanned · 44 skipped</span>
          <span className="text-[11px] font-semibold text-[var(--color-success)]">↑ 3 new</span>
        </div>
      </div>
    </div>
  );
}

// ── Features data ──────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Filter,
    title: "Filters out what you've already read",
    desc: "Every new article is compared to your history. Duplicate stories — no matter the outlet — are silently skipped.",
  },
  {
    icon: BookOpen,
    title: "Tracks how stories develop",
    desc: "Related updates are grouped into ongoing threads so you never lose the thread of a developing situation.",
  },
  {
    icon: Clock,
    title: "Measures time saved",
    desc: "We log every article we skip on your behalf. Most users reclaim 3–5 hours of reading per week.",
  },
  {
    icon: Globe,
    title: "Covers 40+ sources",
    desc: "RSS, Google News, Brave Search, Exa — normalised into one ranked signal. No important outlet is missed.",
  },
  {
    icon: Lock,
    title: "Your topics stay private",
    desc: "Pro and Power users get fully private topics. Free topics are anonymised and never shared.",
  },
  {
    icon: Zap,
    title: "Scans as fast as you need",
    desc: "Daily on Free, hourly on Pro, every 15 minutes on Power — matched to how fast your stories move.",
  },
];

// ── How it works steps ─────────────────────────────────────────────────────

const STEPS = [
  {
    n: "1",
    title: "Choose a topic",
    desc: "Enter any subject — a company, a market, a technology, an ongoing news story.",
  },
  {
    n: "2",
    title: "We monitor the web",
    desc: "Our system continuously scans hundreds of sources and filters out anything you've already seen.",
  },
  {
    n: "3",
    title: "Read only what's new",
    desc: "You receive a concise brief containing only genuinely new facts — nothing repeated.",
  },
];

// ── Pricing data ───────────────────────────────────────────────────────────

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    desc: "Try it with 2 topics. No credit card needed.",
    features: ["2 tracked topics", "Daily scans", "RSS & web sources", "Shareable briefs"],
    cta: "Get Started Free",
    href: "/sign-up",
    featured: false,
  },
  {
    name: "Pro",
    price: "$19",
    period: "/ month",
    desc: "For professionals who need deeper, faster coverage.",
    features: ["15 topics", "Hourly scans", "Google News, Brave & Exa", "Private topics", "Priority processing"],
    cta: "Start Pro",
    href: "/sign-up",
    featured: true,
  },
  {
    name: "Power",
    price: "$49",
    period: "/ month",
    desc: "Unlimited topics and near-real-time scanning.",
    features: ["Unlimited topics", "Scans every 15 min", "All source layers", "Private topics", "Early API access"],
    cta: "Go Power",
    href: "/sign-up",
    featured: false,
  },
];

// ── Page ───────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="bg-[var(--color-surface)] overflow-x-hidden">

      {/* ══ Hero ══════════════════════════════════════════════════════════ */}
      <section className="relative pt-24 pb-16 md:pt-36 md:pb-24">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 70% 40% at 50% 0%, oklch(0.55 0.22 264 / 0.06), transparent)' }} />

        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] mb-8 shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-success)] animate-pulse inline-block" />
            AI-powered news monitoring · Free to start
          </div>

          {/* Headline */}
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight text-[var(--color-text)] leading-[1.05] mb-6">
            All the signal.
            <br />
            <span style={{ color: 'oklch(0.55 0.22 264)' }}>None of the noise.</span>
          </h1>

          {/* Subtext */}
          <p className="max-w-lg mx-auto text-lg text-[var(--color-text-secondary)] leading-relaxed mb-10">
            TrueBrief monitors any topic around the clock and delivers only what's genuinely new since your last read.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row justify-center gap-3 mb-6">
            <Link
              href="/sign-up"
              className="inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold text-white shadow-md transition-all active:scale-[0.98] hover:opacity-90"
              style={{ background: 'oklch(0.55 0.22 264)' }}
            >
              Start for Free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-6 py-3 text-sm font-semibold text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-surface-overlay)]"
            >
              Open Dashboard
            </Link>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">No credit card · Free plan available</p>

          {/* Product preview */}
          <div className="mt-16">
            <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-widest mb-5">
              What a brief looks like
            </p>
            <BriefPreviewCard />
          </div>
        </div>
      </section>

      {/* ══ Stats bar ═════════════════════════════════════════════════════ */}
      <div className="border-y border-[var(--color-border)] bg-[var(--color-surface-raised)]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-3 gap-6 text-center">
            {[
              { value: '40+', label: 'news sources monitored' },
              { value: '3–5h', label: 'saved per user per week' },
              { value: '0', label: 'repeated stories' },
            ].map(({ value, label }) => (
              <div key={label}>
                <p className="text-2xl md:text-3xl font-bold text-[var(--color-text)]">{value}</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ══ How it works ══════════════════════════════════════════════════ */}
      <section className="py-24 bg-[var(--color-surface)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">How it works</p>
            <h2 className="text-3xl md:text-4xl font-bold text-[var(--color-text)] tracking-tight">
              From topic to insight in 3 steps
            </h2>
          </div>

          <div className="relative grid md:grid-cols-3 gap-10">
            {/* Connecting line — desktop only */}
            <div className="hidden md:block absolute top-5 left-[calc(16.67%+1rem)] right-[calc(16.67%+1rem)] h-px border-t border-dashed border-[var(--color-border)]" />

            {STEPS.map((step) => (
              <div key={step.n} className="relative flex flex-col items-center text-center md:items-center">
                <div
                  className="relative z-10 mb-6 flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold text-white shadow-md"
                  style={{ background: 'oklch(0.55 0.22 264)' }}
                >
                  {step.n}
                </div>
                <h3 className="text-base font-semibold text-[var(--color-text)] mb-2">{step.title}</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed max-w-[240px]">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ Features ══════════════════════════════════════════════════════ */}
      <section className="py-24 bg-[var(--color-surface-raised)] border-y border-[var(--color-border)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">Features</p>
            <h2 className="text-3xl md:text-4xl font-bold text-[var(--color-text)] tracking-tight">
              Built to reduce what you read,<br className="hidden md:block" /> not add to it
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 hover:border-[var(--color-brand)] hover:shadow-md transition-all duration-200"
              >
                <div
                  className="mb-4 inline-flex h-9 w-9 items-center justify-center rounded-lg"
                  style={{ background: 'oklch(0.55 0.22 264 / 0.08)' }}
                >
                  <f.icon className="h-4 w-4" style={{ color: 'oklch(0.55 0.22 264)' }} />
                </div>
                <h3 className="text-sm font-semibold text-[var(--color-text)] mb-2 leading-snug">{f.title}</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ Pricing ═══════════════════════════════════════════════════════ */}
      <section id="pricing" className="py-24 bg-[var(--color-surface)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">Pricing</p>
            <h2 className="text-3xl md:text-4xl font-bold text-[var(--color-text)] tracking-tight">
              Simple pricing, no surprises
            </h2>
            <p className="mt-3 text-[var(--color-text-secondary)] text-base">
              Start free. Upgrade when you need more.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-4 items-start">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl border p-7 transition-all ${
                  plan.featured
                    ? 'border-[var(--color-brand)] shadow-xl md:scale-105'
                    : 'border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-sm'
                }`}
                style={plan.featured ? { background: 'oklch(0.55 0.22 264)' } : undefined}
              >
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-white text-[11px] font-bold shadow-sm"
                    style={{ color: 'oklch(0.55 0.22 264)' }}>
                    Most Popular
                  </div>
                )}

                <p className={`text-xs font-semibold uppercase tracking-widest mb-3 ${plan.featured ? 'text-white/60' : 'text-[var(--color-text-muted)]'}`}>
                  {plan.name}
                </p>
                <div className="flex items-baseline gap-1 mb-2">
                  <span className={`text-4xl font-bold ${plan.featured ? 'text-white' : 'text-[var(--color-text)]'}`}>{plan.price}</span>
                  <span className={`text-sm ${plan.featured ? 'text-white/50' : 'text-[var(--color-text-muted)]'}`}>{plan.period}</span>
                </div>
                <p className={`text-sm mb-7 leading-relaxed ${plan.featured ? 'text-white/75' : 'text-[var(--color-text-secondary)]'}`}>{plan.desc}</p>

                <ul className="space-y-2.5 mb-8">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-2.5">
                      <CheckCircle className={`h-4 w-4 shrink-0 ${plan.featured ? 'text-white/60' : 'text-[var(--color-brand)]'}`} />
                      <span className={`text-sm ${plan.featured ? 'text-white/90' : 'text-[var(--color-text-secondary)]'}`}>{feat}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.href}
                  className={`block w-full text-center rounded-xl py-3 text-sm font-semibold transition-all active:scale-[0.98] ${
                    plan.featured
                      ? 'bg-white hover:bg-white/90'
                      : 'bg-[var(--color-brand)] text-white hover:opacity-90 shadow-sm'
                  }`}
                  style={plan.featured ? { color: 'oklch(0.55 0.22 264)' } : undefined}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ Bottom CTA ════════════════════════════════════════════════════ */}
      <section className="py-24 relative overflow-hidden"
        style={{ background: 'oklch(0.14 0 0)' }}>
        {/* Subtle glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 100%, oklch(0.55 0.22 264 / 0.15), transparent)' }} />

        <div className="relative max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-5"
            style={{ color: 'oklch(0.96 0 0)' }}>
            Read less.<br />Know more.
          </h2>
          <p className="text-base leading-relaxed mb-10 max-w-md mx-auto"
            style={{ color: 'oklch(0.60 0 0)' }}>
            Join analysts, founders, and researchers who've reclaimed hours of reading time without missing a single important development.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 rounded-xl px-7 py-3.5 text-sm font-semibold text-white shadow-lg transition-all active:scale-[0.98] hover:opacity-90"
            style={{ background: 'oklch(0.55 0.22 264)' }}
          >
            Get Your First Brief Free <ArrowRight className="h-4 w-4" />
          </Link>
          <p className="mt-5 text-xs" style={{ color: 'oklch(0.50 0 0)' }}>
            No credit card · Cancel anytime
          </p>
        </div>
      </section>
    </div>
  );
}
