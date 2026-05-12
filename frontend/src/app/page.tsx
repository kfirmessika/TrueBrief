import Link from "next/link";
import { ArrowRight, Zap, BookOpen, Clock, CheckCircle, Globe, Lock } from "lucide-react";

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Add a Topic",
    desc: "Type any subject you want to track — a company, a technology, a geopolitical situation. We build smart search queries automatically.",
  },
  {
    step: "02",
    title: "We Scan the Web",
    desc: "Our pipeline scours RSS feeds, Google News, and the open web. Every article is compared to what you've already read.",
  },
  {
    step: "03",
    title: "Get the Delta",
    desc: "You receive a brief containing only the net-new facts. No repeats. No noise. Just what changed since your last read.",
  },
];

const FEATURES = [
  {
    icon: Zap,
    title: "Delta Detection",
    desc: "Vector-similarity AI compares every incoming article to your existing knowledge base. You only see facts you haven't seen before.",
  },
  {
    icon: BookOpen,
    title: "Smart Story Nodes",
    desc: "Alphas are grouped into evolving story threads. Watch a situation develop across weeks without sifting through duplicate reports.",
  },
  {
    icon: Clock,
    title: "Time Saved, Quantified",
    desc: "We track every skipped article. Most users reclaim 3–5 hours of reading per week — and we show you the exact number.",
  },
  {
    icon: Globe,
    title: "Multi-Source Coverage",
    desc: "RSS, Google News, Tavily, Brave Search, and Exa — all normalised into a single ranked signal. No source is missed.",
  },
  {
    icon: Lock,
    title: "Private Topics",
    desc: "Pro and Power users get private topics — your intel stays yours. Free tier topics are anonymised for research improvements.",
  },
  {
    icon: CheckCircle,
    title: "Tier-Speed Scanning",
    desc: "Free users get daily scans. Pro users scan hourly. Power users push the limit to every 15 minutes for fast-moving stories.",
  },
];

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Try TrueBrief with 2 topics. No credit card required.",
    features: [
      "2 topics",
      "Daily scans (every 24h)",
      "RSS & Tavily sources",
      "Public topic index",
    ],
    cta: "Get Started Free",
    href: "/sign-up",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$19",
    period: "/ month",
    description: "For professionals who need deep, hourly intel coverage.",
    features: [
      "15 topics",
      "Hourly scans",
      "5 source layers incl. Google News, Brave, Exa",
      "Private topics",
      "Priority processing",
    ],
    cta: "Start Pro",
    href: "/sign-up",
    highlight: true,
  },
  {
    name: "Power",
    price: "$49",
    period: "/ month",
    description: "Unlimited topics and near-real-time scanning for analysts.",
    features: [
      "Unlimited topics",
      "Scans every 15 minutes",
      "All source layers",
      "Private topics",
      "API access (coming soon)",
    ],
    cta: "Go Power",
    href: "/sign-up",
    highlight: false,
  },
];

export default function LandingPage() {
  return (
    <div className="bg-white">
      {/* ── Hero ── */}
      <section className="relative py-24 md:py-32 overflow-hidden bg-gradient-to-b from-slate-50 to-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-50/60 via-transparent to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
          <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 px-4 py-2 rounded-full text-sm font-bold mb-8 border border-indigo-100">
            <Zap className="h-3.5 w-3.5" /> AI-powered delta intelligence
          </div>
          <h1 className="text-5xl md:text-7xl font-black tracking-tight text-slate-900 mb-6 leading-tight">
            Stop reading the news.
            <br />
            <span className="text-indigo-600">Get the delta.</span>
          </h1>
          <p className="max-w-2xl mx-auto text-xl text-slate-500 font-medium mb-10 leading-relaxed">
            TrueBrief scans the internet 24/7 and delivers only what changed
            since you last checked. No repeats. No noise. Just new facts.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link
              href="/sign-up"
              className="inline-flex items-center justify-center gap-2 bg-indigo-600 text-white px-8 py-4 rounded-2xl text-lg font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-200 active:scale-95"
            >
              Start Free — No Card Required <ArrowRight className="h-5 w-5" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 bg-white text-slate-800 border-2 border-slate-200 px-8 py-4 rounded-2xl text-lg font-bold hover:bg-slate-50 transition-all"
            >
              View Dashboard
            </Link>
          </div>
          <p className="mt-6 text-sm text-slate-400 font-medium">
            Free plan · 2 topics · No credit card
          </p>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="py-24 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-slate-900 tracking-tight mb-4">
              How it works
            </h2>
            <p className="text-slate-500 font-medium text-lg max-w-xl mx-auto">
              From topic to intelligence brief in three steps.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {HOW_IT_WORKS.map((item) => (
              <div key={item.step} className="relative">
                <div className="text-7xl font-black text-indigo-50 leading-none mb-4 select-none">
                  {item.step}
                </div>
                <h3 className="text-xl font-black text-slate-900 mb-3 -mt-6">
                  {item.title}
                </h3>
                <p className="text-slate-500 font-medium leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="py-24 bg-slate-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-slate-900 tracking-tight mb-4">
              Built for signal, not volume
            </h2>
            <p className="text-slate-500 font-medium text-lg max-w-xl mx-auto">
              Every feature is designed to reduce what you read, not increase it.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="bg-white rounded-3xl p-8 border border-slate-100 shadow-sm hover:shadow-md transition-all"
              >
                <div className="bg-indigo-50 p-3 rounded-2xl w-fit mb-6">
                  <feature.icon className="h-5 w-5 text-indigo-600" />
                </div>
                <h3 className="text-lg font-black text-slate-900 mb-3">
                  {feature.title}
                </h3>
                <p className="text-slate-500 font-medium leading-relaxed text-sm">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="py-24 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-slate-900 tracking-tight mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-slate-500 font-medium text-lg max-w-xl mx-auto">
              Start free. Upgrade when you need faster scans or more topics.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-3xl p-8 border transition-all ${
                  plan.highlight
                    ? "bg-indigo-600 border-indigo-600 shadow-2xl shadow-indigo-200 scale-105"
                    : "bg-white border-slate-100 shadow-sm"
                }`}
              >
                <div className="mb-6">
                  <p
                    className={`text-sm font-bold uppercase tracking-widest mb-2 ${
                      plan.highlight ? "text-indigo-200" : "text-slate-400"
                    }`}
                  >
                    {plan.name}
                  </p>
                  <div className="flex items-baseline gap-1">
                    <span
                      className={`text-4xl font-black ${
                        plan.highlight ? "text-white" : "text-slate-900"
                      }`}
                    >
                      {plan.price}
                    </span>
                    <span
                      className={`font-medium ${
                        plan.highlight ? "text-indigo-200" : "text-slate-400"
                      }`}
                    >
                      {plan.period}
                    </span>
                  </div>
                  <p
                    className={`mt-3 text-sm font-medium leading-relaxed ${
                      plan.highlight ? "text-indigo-100" : "text-slate-500"
                    }`}
                  >
                    {plan.description}
                  </p>
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-3">
                      <CheckCircle
                        className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                          plan.highlight ? "text-indigo-200" : "text-indigo-500"
                        }`}
                      />
                      <span
                        className={`text-sm font-medium ${
                          plan.highlight ? "text-indigo-100" : "text-slate-600"
                        }`}
                      >
                        {f}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.href}
                  className={`block text-center py-3.5 px-6 rounded-2xl font-black text-sm transition-all active:scale-95 ${
                    plan.highlight
                      ? "bg-white text-indigo-600 hover:bg-indigo-50"
                      : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg shadow-indigo-100"
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Bottom CTA ── */}
      <section className="py-24 bg-slate-900">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl md:text-5xl font-black text-white tracking-tight mb-6">
            Read less. Know more.
          </h2>
          <p className="text-slate-400 font-medium text-xl mb-10 max-w-xl mx-auto leading-relaxed">
            Join analysts, founders, and researchers who've cut their news
            reading time by 80% without missing a single important development.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 bg-indigo-600 text-white px-10 py-5 rounded-2xl text-lg font-black hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-900/50 active:scale-95"
          >
            Get Your First Brief Free <ArrowRight className="h-5 w-5" />
          </Link>
          <p className="mt-6 text-slate-500 text-sm font-medium">
            No credit card · Free forever plan · Cancel anytime
          </p>
        </div>
      </section>
    </div>
  );
}
