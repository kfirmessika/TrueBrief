'use client';

import { AlertTriangle } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-[oklch(0_0_0/0.5)] backdrop-blur-sm">
      <div className="bg-[var(--color-surface-raised)] rounded-2xl p-6 max-w-md w-full shadow-xl border border-[var(--color-border)]">
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-[var(--color-warning-subtle)] p-2.5 rounded-xl">
            <AlertTriangle className="h-5 w-5 text-[var(--color-warning)]" />
          </div>
          <h3 className="text-base font-bold text-[var(--color-text)]">{title}</h3>
        </div>

        <p className="text-sm text-[var(--color-text-secondary)] mb-6 leading-relaxed">
          {description}
        </p>

        <div className="flex flex-col sm:flex-row gap-2.5">
          <button
            onClick={onCancel}
            className="flex-1 px-5 py-2.5 rounded-xl text-sm font-semibold text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-5 py-2.5 rounded-xl text-sm font-semibold bg-[var(--color-danger)] text-white hover:opacity-90 transition-opacity shadow-sm"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
