import { Zap } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface-raised)] mt-auto">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-[var(--color-brand)]" />
            <span className="text-sm font-bold text-[var(--color-text)]">TrueBrief</span>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            © {new Date().getFullYear()} TrueBrief Intelligence. All rights reserved.
          </p>
          <div className="flex gap-5">
            <a href="#" className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-brand)] transition-colors">Privacy</a>
            <a href="#" className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-brand)] transition-colors">Terms</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
