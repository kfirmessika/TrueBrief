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
    } catch (err) {
      // Error handling is managed by the parent via toast
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative group">
      <div className="absolute left-4 top-1/2 -translate-y-1/2 bg-slate-100 p-2 rounded-xl group-focus-within:bg-indigo-100 transition-colors">
        <Plus className="h-5 w-5 text-slate-400 group-focus-within:text-indigo-600" />
      </div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Track a new topic (e.g. 'Bitcoin ETFs', 'AI Safety Bill')..."
        className="w-full pl-16 pr-32 py-5 bg-white border-2 border-slate-100 rounded-3xl focus:border-indigo-600 focus:outline-none transition-all text-lg font-medium shadow-sm"
        disabled={isLoading}
      />
      <div className="absolute right-3 top-1/2 -translate-y-1/2">
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="bg-indigo-600 text-white px-6 py-2.5 rounded-2xl font-bold hover:bg-indigo-700 disabled:bg-slate-100 disabled:text-slate-400 transition-all flex items-center gap-2 shadow-sm shadow-indigo-100"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Adding...
            </>
          ) : (
            'Add Topic'
          )}
        </button>
      </div>
    </form>
  );
}
