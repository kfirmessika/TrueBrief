'use client';

import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  override componentDidCatch(error: Error) {
    console.error('[ErrorBoundary]', error);
  }

  override render() {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
        <div className="mb-4 rounded-2xl bg-[var(--color-danger-subtle)] p-4">
          <AlertTriangle className="h-8 w-8 text-[var(--color-danger)]" strokeWidth={1.5} />
        </div>
        <h3 className="text-base font-semibold text-[var(--color-text)]">Something went wrong</h3>
        <p className="mt-1 max-w-sm text-sm text-[var(--color-text-secondary)]">
          {this.state.message || 'An unexpected error occurred. Try refreshing.'}
        </p>
        <button
          onClick={() => this.setState({ hasError: false, message: '' })}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-brand)] px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Try again
        </button>
      </div>
    );
  }
}
