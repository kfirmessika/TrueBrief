'use client';

import { useState, useCallback } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useApi } from '@/lib/useApi';
import { cn } from '@/lib/utils';

type ScanState = 'idle' | 'queuing' | 'running' | 'done' | 'error';

interface ScanButtonProps {
  topicId: string;
  className?: string;
  onComplete?: () => void;
}

export default function ScanButton({ topicId, className, onComplete }: ScanButtonProps) {
  const api = useApi();
  const [state, setState] = useState<ScanState>('idle');
  const [message, setMessage] = useState('');

  const poll = useCallback(async (taskId: string) => {
    let attempts = 0;
    const MAX_ATTEMPTS = 120; // 4 min at 2s intervals

    const tick = async () => {
      if (attempts >= MAX_ATTEMPTS) {
        setState('error');
        setMessage('Scan timed out');
        return;
      }
      attempts++;
      try {
        const res = await api.get(`/scan-status/${taskId}`);
        const { state: taskState } = res.data;

        if (taskState === 'SUCCESS') {
          setState('done');
          setMessage('Brief ready');
          onComplete?.();
          setTimeout(() => setState('idle'), 4000);
        } else if (taskState === 'FAILURE') {
          setState('error');
          setMessage('Scan failed');
          setTimeout(() => setState('idle'), 4000);
        } else {
          setTimeout(tick, 2000);
        }
      } catch {
        setState('error');
        setMessage('Connection error');
        setTimeout(() => setState('idle'), 4000);
      }
    };

    tick();
  }, [api, onComplete]);

  const handleScan = async () => {
    if (state !== 'idle') return;
    setState('queuing');
    setMessage('');
    try {
      const res = await api.post(`/topics/${topicId}/scan`);
      setState('running');
      poll(res.data.task_id);
    } catch {
      setState('error');
      setMessage('Could not start scan');
      setTimeout(() => setState('idle'), 4000);
    }
  };

  const icons: Record<ScanState, React.ReactNode> = {
    idle:    <Play className="h-4 w-4 fill-current" />,
    queuing: <Loader2 className="h-4 w-4 animate-spin" />,
    running: <Loader2 className="h-4 w-4 animate-spin" />,
    done:    <CheckCircle2 className="h-4 w-4" />,
    error:   <AlertCircle className="h-4 w-4" />,
  };

  const labels: Record<ScanState, string> = {
    idle:    'Scan Now',
    queuing: 'Queuing…',
    running: 'Scanning…',
    done:    message || 'Done',
    error:   message || 'Error',
  };

  const colorMap: Record<ScanState, string> = {
    idle:    'bg-[var(--color-brand)] hover:bg-[var(--color-brand-dark)] text-white shadow-sm',
    queuing: 'bg-[var(--color-brand)] text-white opacity-80 cursor-wait',
    running: 'bg-[var(--color-brand)] text-white opacity-80 cursor-wait',
    done:    'bg-[var(--color-success)] text-white',
    error:   'bg-[var(--color-danger)] text-white',
  };

  return (
    <button
      onClick={handleScan}
      disabled={state !== 'idle'}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200',
        colorMap[state],
        className
      )}
    >
      {icons[state]}
      {labels[state]}
    </button>
  );
}
