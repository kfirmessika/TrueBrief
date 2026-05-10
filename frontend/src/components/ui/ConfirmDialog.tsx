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
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl border border-slate-100 animate-in zoom-in-95">
        <div className="flex items-center gap-4 mb-6">
          <div className="bg-amber-100 p-3 rounded-2xl">
            <AlertTriangle className="h-6 w-6 text-amber-600" />
          </div>
          <h3 className="text-xl font-bold text-slate-900">{title}</h3>
        </div>
        
        <p className="text-slate-600 mb-8 leading-relaxed">
          {description}
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={onCancel}
            className="flex-grow px-6 py-3 rounded-xl font-bold text-slate-600 hover:bg-slate-50 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="flex-grow px-6 py-3 rounded-xl font-bold bg-red-600 text-white hover:bg-red-700 transition-colors shadow-lg shadow-red-100"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
