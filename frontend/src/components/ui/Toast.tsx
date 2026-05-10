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

  const bgColors = {
    error: 'bg-red-600',
    success: 'bg-green-600',
    info: 'bg-indigo-600',
  };

  return (
    <div className={`fixed bottom-4 right-4 ${bgColors[type]} text-white px-6 py-4 rounded-2xl shadow-2xl z-[100] flex items-center gap-4 animate-in fade-in slide-in-from-bottom-4`}>
      <span className="font-medium">{message}</span>
      <button onClick={onClose} className="p-1 hover:bg-white/20 rounded-full transition-colors">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * Simple hook-like state for managing a single toast.
 * In a real app, we'd use a context or a dedicated lib.
 */
export function useToast() {
  const [toast, setToast] = useState<{ message: string; type: 'error' | 'success' | 'info' } | null>(null);

  const showToast = (message: string, type: 'error' | 'success' | 'info' = 'info') => {
    setToast({ message, type });
  };

  const hideToast = () => setToast(null);

  return { toast, showToast, hideToast };
}
