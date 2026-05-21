'use client';

import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ToastProps {
  message: string;
  type?: 'error' | 'success' | 'info';
  onClose: () => void;
  duration?: number;
}

export function Toast({ message, type = 'info', onClose, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const bgClass = {
    error: 'bg-[var(--color-danger)]',
    success: 'bg-[var(--color-success)]',
    info: 'bg-[var(--color-brand)]',
  }[type];

  return (
    <div className={`fixed bottom-4 right-4 ${bgClass} text-white px-5 py-3.5 rounded-xl shadow-xl z-[100] flex items-center gap-3 text-sm font-medium`}>
      <span>{message}</span>
      <button onClick={onClose} className="p-1 hover:bg-white/20 rounded-lg transition-colors">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function useToast() {
  const [toast, setToast] = useState<{ message: string; type: 'error' | 'success' | 'info' } | null>(null);

  const showToast = (message: string, type: 'error' | 'success' | 'info' = 'info') => {
    setToast({ message, type });
  };

  const hideToast = () => setToast(null);

  return { toast, showToast, hideToast };
}
