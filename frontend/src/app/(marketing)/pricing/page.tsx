import Link from "next/link";
import { Check } from "lucide-react";

export const metadata = {
  title: "Pricing — TrueBrief",
  description: "Simple plans for noise-free news intelligence. Start free.",
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface TierDef {
  max_topics: number;
  min_interval_hours: number;
  private_topics: boolean;
  api_calls_per_day: number;
  max_scans_per_day?: number;
  price_usd_month?: number;
}

async function getTiers(): Promise<Record<string, TierDef> | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/billing/tiers`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function price(t?: TierDef): string {
  if (!t || !t.price_usd_month) return "";
  return `$${t.price_usd_month}`;
}

function topics(t?: TierDef): string {
  if (!t) return "—";
  return t.max_topics === -1 ? "Unlimited topics" : `${t.max_topics} topics`;
}

function cadence(t?: TierDef): string {
  if (!t) return "—";
  const h = t.min_interval_hours;
  if (h >= 24) return "1 scan / day per topic";
  if (h >= 1) return `Scans as often as every ${h}h`;
  return "Scans as often as every 15 min";
}

const PLANS = [
  {
    key: "free",
    name: "Free",
    blurb: "Track a couple of stories, one refresh a day.",
    cta: { label: "Start free", href: "/sign-up" },
    highlight: false,
  },
  {
    key: "pro",
    name: "Pro",
    blurb: "For people who follow a lot of stories closely.",
    cta: { label: "Go Pro", href: "/settings" },
    highlight: true,
  },
  {
    key: "power",
    name: "Power",
    blurb: "Unlimited topics, fastest refresh, full API.",
    cta: { label: "Go Power", href: "/settings" },
    highlight: false,
  },
];

export default async function PricingPage() {
  const tiers = await getTiers();

  return (
    <div className="bg-[var(--color-surface)]">
      <section className="pt-20 pb-14 md:pt-28">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-xs font-semibold text-[var(--color-brand)] uppercase tracking-widest mb-3">
            Pricing
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[var(--color-text)] mb-4">
            One number, no surprises.
          </h1>
          <p className="text-lg text-[var(--color-text-secondary)] max-w-xl mb-12">
            Every plan gets the same deduplicated, source-checked fact stream. Paid
            plans add more topics and faster refreshes. Cancel anytime.
          </p>

          <div className="grid gap-5 md:grid-cols-3">
            {PLANS.map((plan) => {
              const t = tiers?.[plan.key];
              const p = price(t);
              return (
                <div
                  key={plan.key}
                  className={`rounded-2xl border p-6 flex flex-col ${
                    plan.highlight
                      ? "border-[var(--color-brand)] shadow-sm"
                      : "border-[var(--color-border)]"
                  }`}
                >
                  <h2 className="text-lg font-semibold text-[var(--color-text)]">{plan.name}</h2>
                  <div className="mt-2 mb-1 h-9 flex items-baseline gap-1">
                    {plan.key === "free" ? (
                      <span className="text-3xl font-bold text-[var(--color-text)]">Free</span>
                    ) : p ? (
                      <>
                        <span className="text-3xl font-bold text-[var(--color-text)]">{p}</span>
                        <span className="text-sm text-[var(--color-text-secondary)]">/ month</span>
                      </>
                    ) : (
                      <span className="text-sm text-[var(--color-text-secondary)]">
                        See checkout for current price
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] text-[var(--color-text-secondary)] mb-5">{plan.blurb}</p>

                  <ul className="space-y-2 mb-6 text-[13px] text-[var(--color-text-secondary)]">
                    <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-[var(--color-brand)]" />{topics(t)}</li>
                    <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-[var(--color-brand)]" />{cadence(t)}</li>
                    {t?.private_topics && (
                      <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-[var(--color-brand)]" />Private topics</li>
                    )}
                    {!!t?.api_calls_per_day && t.api_calls_per_day !== 0 && (
                      <li className="flex gap-2">
                        <Check size={15} className="mt-0.5 shrink-0 text-[var(--color-brand)]" />
                        Developer API{t.api_calls_per_day === -1 ? "" : ` — ${t.api_calls_per_day.toLocaleString()} calls/day`}
                      </li>
                    )}
                  </ul>

                  <Link
                    href={plan.cta.href}
                    className={`mt-auto inline-flex justify-center rounded-xl px-4 py-2 text-sm font-semibold ${
                      plan.highlight
                        ? "bg-[var(--color-brand)] text-white"
                        : "border border-[var(--color-border)] text-[var(--color-text)]"
                    }`}
                  >
                    {plan.cta.label}
                  </Link>
                </div>
              );
            })}
          </div>

          <p className="text-[12px] text-[var(--color-text-tertiary)] mt-8">
            Billing is handled by Paddle, our merchant of record. Prices shown are per
            month in USD.
          </p>
        </div>
      </section>
    </div>
  );
}
