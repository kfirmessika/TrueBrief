import Link from 'next/link';
import { ArrowRight, CheckCircle2, Zap } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="bg-white">
      {/* Hero Section */}
      <section className="relative py-20 overflow-hidden bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center">
            <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-slate-900 mb-6">
              Stop reading the news. <br />
              <span className="text-indigo-600">Get the brief.</span>
            </h1>
            <p className="max-w-2xl mx-auto text-xl text-slate-600 mb-10">
              TrueBrief watches the internet 24/7 and delivers only what's new. 
              No noise, no repeats, just the delta.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link 
                href="/dashboard" 
                className="bg-indigo-600 text-white px-8 py-4 rounded-xl text-lg font-bold hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
              >
                Start Your First Topic <ArrowRight className="h-5 w-5" />
              </Link>
              <button className="bg-white text-slate-900 border-2 border-slate-200 px-8 py-4 rounded-xl text-lg font-bold hover:bg-slate-50 transition-all">
                View Sample Brief
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-3 gap-12">
          {[
            {
              title: "Delta Detection",
              desc: "Our AI compares every new article to what you've already read. You only see the new facts.",
              icon: Zap
            },
            {
              title: "Smart Stories",
              desc: "Alphas are grouped into evolving story nodes. Watch a situation develop without the clutter.",
              icon: CheckCircle2
            },
            {
              title: "Time Saved",
              desc: "Save hours every week by skipping redundant content. We quantify exactly how much time you save.",
              icon: Zap
            }
          ].map((feature, i) => (
            <div key={i} className="p-8 rounded-2xl bg-slate-50 hover:shadow-lg transition-all border border-slate-100">
              <div className="bg-white p-3 rounded-xl w-fit shadow-sm mb-6">
                <feature.icon className="h-6 w-6 text-indigo-600" />
              </div>
              <h3 className="text-xl font-bold mb-4 text-slate-900">{feature.title}</h3>
              <p className="text-slate-600 leading-relaxed">{feature.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
