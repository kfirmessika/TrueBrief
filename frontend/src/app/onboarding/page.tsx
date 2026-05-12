'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, CheckCircle, ArrowRight, Zap, Search } from 'lucide-react';
import { useTopics, useCreateTopic, useTriggerScan } from '@/hooks/useTopics';

type Step = 1 | 2 | 3;

const EXAMPLE_QUERIES = [
  'NVIDIA Earnings',
  'Ukraine War',
  'iPhone 17 Leaks',
  'Fed Interest Rates',
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [createdTopicName, setCreatedTopicName] = useState('');

  const { data: topics, isLoading: topicsLoading } = useTopics();
  const createMutation = useCreateTopic();
  const scanMutation = useTriggerScan();

  useEffect(() => {
    if (!topicsLoading && topics && topics.length > 0) {
      router.replace('/dashboard');
    }
  }, [topics, topicsLoading, router]);

  const handleSubmit = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    setCreatedTopicName(trimmed);
    setStep(2);
    try {
      const topic = await createMutation.mutateAsync(trimmed);
      // Fire-and-forget: kick off first scan without blocking UI
      scanMutation.mutate(topic.id);
      setStep(3);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to create topic. Please try again.';
      setError(detail);
      setStep(1);
    }
  };

  if (topicsLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div className="bg-indigo-50 text-indigo-700 px-4 py-1.5 rounded-full text-sm font-bold w-fit mx-auto mb-6">
        Step {step} of 3
      </div>

      {step === 1 && (
        <StepOne
          query={query}
          setQuery={setQuery}
          error={error}
          onSubmit={handleSubmit}
          onSkip={() => router.push('/dashboard')}
        />
      )}

      {step === 2 && <StepTwo topicName={createdTopicName} />}

      {step === 3 && (
        <StepThree
          topicName={createdTopicName}
          onDone={() => router.push('/dashboard')}
        />
      )}
    </div>
  );
}

// ─── Step 1: Enter topic ──────────────────────────────────────────────────────

interface StepOneProps {
  query: string;
  setQuery: (v: string) => void;
  error: string | null;
  onSubmit: () => void;
  onSkip: () => void;
}

function StepOne({ query, setQuery, error, onSubmit, onSkip }: StepOneProps) {
  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && query.trim()) onSubmit();
  };

  return (
    <>
      <h1 className="text-4xl font-extrabold text-slate-900 mb-4">
        Welcome to TrueBrief
      </h1>
      <p className="text-xl text-slate-600 mb-10">
        Let&apos;s get your intelligence pipeline running. What&apos;s the first
        thing you want to track?
      </p>

      <div className="relative mb-4">
        <Search className="absolute left-5 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder="e.g. NVIDIA Earnings, Ukraine War, iPhone 17 Leaks"
          className="w-full pl-14 pr-6 py-5 rounded-2xl border-2 border-slate-200 focus:border-indigo-600 focus:outline-none text-lg transition-colors shadow-sm"
          autoFocus
        />
      </div>

      <div className="flex flex-wrap gap-2 justify-center mb-8">
        {EXAMPLE_QUERIES.map((ex) => (
          <button
            key={ex}
            onClick={() => setQuery(ex)}
            className="px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-sm font-medium hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-red-600 text-sm font-medium mb-4 bg-red-50 px-4 py-2 rounded-xl">
          {error}
        </p>
      )}

      <button
        onClick={onSubmit}
        disabled={!query.trim()}
        className="w-full bg-indigo-600 text-white py-5 rounded-2xl text-xl font-bold hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 mb-6 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-3"
      >
        Build My First Brief
        <ArrowRight className="h-5 w-5" />
      </button>

      <button
        onClick={onSkip}
        className="text-slate-400 font-medium hover:text-slate-600 transition-colors"
      >
        Skip and go to dashboard
      </button>
    </>
  );
}

// ─── Step 2: Loading / creating ───────────────────────────────────────────────

function StepTwo({ topicName }: { topicName: string }) {
  return (
    <>
      <div className="flex justify-center mb-8">
        <div className="bg-indigo-50 p-6 rounded-[2rem]">
          <Loader2 className="h-14 w-14 text-indigo-600 animate-spin" />
        </div>
      </div>
      <h1 className="text-4xl font-extrabold text-slate-900 mb-4">
        Building your pipeline
      </h1>
      <p className="text-xl text-slate-600">
        We&apos;re spinning up your intelligence feed for{' '}
        <span className="font-bold text-slate-800">&ldquo;{topicName}&rdquo;</span>.
        This takes just a moment.
      </p>
      <div className="mt-10 flex flex-col gap-3 text-left max-w-sm mx-auto">
        {['Creating topic', 'Configuring sources', 'Scheduling first scan'].map(
          (label) => (
            <div key={label} className="flex items-center gap-3 text-slate-500 text-sm font-medium">
              <Loader2 className="h-4 w-4 text-indigo-400 animate-spin shrink-0" />
              {label}…
            </div>
          )
        )}
      </div>
    </>
  );
}

// ─── Step 3: Success ──────────────────────────────────────────────────────────

function StepThree({ topicName, onDone }: { topicName: string; onDone: () => void }) {
  return (
    <>
      <div className="flex justify-center mb-8">
        <div className="bg-green-50 p-6 rounded-[2rem]">
          <CheckCircle className="h-14 w-14 text-green-500" />
        </div>
      </div>
      <h1 className="text-4xl font-extrabold text-slate-900 mb-4">
        Pipeline live!
      </h1>
      <p className="text-xl text-slate-600 mb-3">
        <span className="font-bold text-slate-800">&ldquo;{topicName}&rdquo;</span> is now
        being monitored. Your first brief is generating in the background.
      </p>
      <p className="text-slate-500 mb-10">
        You&apos;ll see it in your dashboard once the scan completes — usually under a
        minute.
      </p>

      <button
        onClick={onDone}
        className="w-full bg-indigo-600 text-white py-5 rounded-2xl text-xl font-bold hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 flex items-center justify-center gap-3"
      >
        <Zap className="h-5 w-5" />
        Go to Dashboard
      </button>
    </>
  );
}
