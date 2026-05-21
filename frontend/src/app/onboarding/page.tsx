'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, CheckCircle, ArrowRight, Zap, Search } from 'lucide-react';
import { useTopics, useCreateTopic, useTriggerScan } from '@/hooks/useTopics';

type Step = 1 | 2 | 3;

const EXAMPLE_QUERIES = [
  'NVIDIA earnings',
  'iPhone 17 leaks',
  'Federal Reserve rates',
  'OpenAI news',
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
        <Loader2 className="h-7 w-7 text-[var(--color-brand)] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-20 text-center">
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 mb-10">
        {([1, 2, 3] as Step[]).map((s) => (
          <div
            key={s}
            className={`h-1.5 rounded-full transition-all duration-300 ${
              s === step
                ? 'w-8 bg-[var(--color-brand)]'
                : s < step
                ? 'w-4 bg-[var(--color-brand)]'
                : 'w-4 bg-[var(--color-border)]'
            }`}
          />
        ))}
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

// ─── Step 1: Choose topic ─────────────────────────────────────────────────────

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
      <h1 className="text-3xl font-bold text-[var(--color-text)] mb-3">
        Welcome to TrueBrief
      </h1>
      <p className="text-[var(--color-text-secondary)] mb-10 leading-relaxed">
        What do you want to stay on top of? Enter a topic and we'll monitor it for you — delivering only what's new each time you check.
      </p>

      <div className="relative mb-4">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-muted)] pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          placeholder="e.g. NVIDIA earnings, Ukraine war, iPhone 17"
          className="w-full pl-11 pr-5 py-4 rounded-xl border-2 border-[var(--color-border)] bg-[var(--color-surface-raised)] focus:border-[var(--color-brand)] focus:outline-none text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] text-sm transition-colors shadow-sm"
          autoFocus
        />
      </div>

      <div className="flex flex-wrap gap-2 justify-center mb-8">
        {EXAMPLE_QUERIES.map((ex) => (
          <button
            key={ex}
            onClick={() => setQuery(ex)}
            className="px-3.5 py-1.5 rounded-full bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)] text-xs font-medium hover:bg-[var(--color-brand-subtle)] hover:text-[var(--color-brand)] transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-[var(--color-danger)] text-sm mb-4 bg-[var(--color-danger-subtle)] px-4 py-2.5 rounded-xl">
          {error}
        </p>
      )}

      <button
        onClick={onSubmit}
        disabled={!query.trim()}
        className="w-full bg-[var(--color-brand)] text-white py-4 rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-all shadow-sm mb-5 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        Start Tracking
        <ArrowRight className="h-4 w-4" />
      </button>

      <button
        onClick={onSkip}
        className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors"
      >
        Skip for now
      </button>
    </>
  );
}

// ─── Step 2: Setting up ───────────────────────────────────────────────────────

function StepTwo({ topicName }: { topicName: string }) {
  return (
    <>
      <div className="flex justify-center mb-8">
        <div className="bg-[var(--color-brand-subtle)] p-5 rounded-2xl">
          <Loader2 className="h-10 w-10 text-[var(--color-brand)] animate-spin" />
        </div>
      </div>
      <h1 className="text-2xl font-bold text-[var(--color-text)] mb-3">
        Setting things up…
      </h1>
      <p className="text-[var(--color-text-secondary)] leading-relaxed">
        We're configuring monitoring for{' '}
        <span className="font-semibold text-[var(--color-text)]">"{topicName}"</span>.
        This takes just a moment.
      </p>
      <div className="mt-8 flex flex-col gap-3 text-left max-w-xs mx-auto">
        {['Creating your topic', 'Connecting sources', 'Scheduling first scan'].map((label) => (
          <div key={label} className="flex items-center gap-3 text-[var(--color-text-muted)] text-sm">
            <Loader2 className="h-3.5 w-3.5 text-[var(--color-brand)] animate-spin shrink-0" />
            {label}…
          </div>
        ))}
      </div>
    </>
  );
}

// ─── Step 3: Done ─────────────────────────────────────────────────────────────

function StepThree({ topicName, onDone }: { topicName: string; onDone: () => void }) {
  return (
    <>
      <div className="flex justify-center mb-8">
        <div className="bg-[var(--color-success-subtle)] p-5 rounded-2xl">
          <CheckCircle className="h-10 w-10 text-[var(--color-success)]" />
        </div>
      </div>
      <h1 className="text-2xl font-bold text-[var(--color-text)] mb-3">
        You're all set!
      </h1>
      <p className="text-[var(--color-text-secondary)] mb-2 leading-relaxed">
        <span className="font-semibold text-[var(--color-text)]">"{topicName}"</span> is now being monitored. Your first brief is being prepared in the background.
      </p>
      <p className="text-sm text-[var(--color-text-muted)] mb-10">
        It usually appears in your dashboard within a minute.
      </p>

      <button
        onClick={onDone}
        className="w-full bg-[var(--color-brand)] text-white py-4 rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-all shadow-sm flex items-center justify-center gap-2"
      >
        <Zap className="h-4 w-4" />
        Go to Dashboard
      </button>
    </>
  );
}
