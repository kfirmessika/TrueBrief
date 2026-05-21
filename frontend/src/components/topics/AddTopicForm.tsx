'use client';

import { useState } from 'react';
import { Plus, Loader2 } from 'lucide-react';

interface AddTopicFormProps {
  onSubmit: (query: string) => Promise<void>;
  isLoading: boolean;
}

export function AddTopicForm({ onSubmit, isLoading }: AddTopicFormProps) {
  const [query, setQuery] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    try {
      await onSubmit(query.trim());
      setQuery('');
    } catch {
      // Error handling managed by parent via toast
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
      <div className="relative flex-grow group">
        <div className="absolute left-3.5 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-[var(--color-surface-overlay)] group-focus-within:bg-[var(--color-brand-subtle)] transition-colors pointer-events-none">
          <Plus className="h-4 w-4 text-[var(--color-text-muted)] group-focus-within:text-[var(--color-brand)]" />
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Track a new topic (e.g. 'Bitcoin ETFs', 'AI Safety Bill')..."
          className="w-full pl-12 pr-4 py-3.5 bg-[var(--color-surface-raised)] border-2 border-[var(--color-border)] rounded-xl focus:border-[var(--color-brand)] focus:outline-none transition-all text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] shadow-sm"
          disabled={isLoading}
        />
      </div>

      <button
        type="submit"
        disabled={!query.trim() || isLoading}
        className="bg-[var(--color-brand)] text-white px-5 py-3.5 rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 shadow-sm shrink-0"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Adding…
          </>
        ) : (
          'Add Topic'
        )}
      </button>
    </form>
  );
}
