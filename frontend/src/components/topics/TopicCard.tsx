'use client';

import { Topic } from '@/lib/api';
import { ScanStatusBadge } from './ScanStatusBadge';
import { Play, History, Trash2, Settings, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface TopicCardProps {
  topic: Topic;
  onScan: (id: string) => Promise<string>; // Returns taskId
  onDelete: (id: string) => void;
}

export function TopicCard({ topic, onScan, onDelete }: TopicCardProps) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const taskId = await onScan(topic.id);
      setActiveTaskId(taskId);
    } catch (err) {
      console.error('Scan trigger failed', err);
    } finally {
      setIsScanning(false);
    }
  };

  const humanizedDate = topic.last_scan_at 
    ? `${formatDistanceToNow(new Date(topic.last_scan_at))} ago`
    : 'Never scanned';

  return (
    <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm hover:shadow-md transition-all group relative">
      <div className="flex justify-between items-start mb-4">
        <div className="flex-grow pr-8">
          <h3 className="text-xl font-bold text-slate-900 group-hover:text-indigo-600 transition-colors truncate">
            {topic.raw_query}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-sm text-slate-400">
            <span>Last scan: {humanizedDate}</span>
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          <button
            aria-label="Settings"
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-xl transition-all md:opacity-0 md:group-hover:opacity-100 focus:opacity-100"
          >
            <Settings className="h-4 w-4" />
          </button>
          <button
            aria-label="Delete Topic"
            onClick={() => onDelete(topic.id)}
            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all md:opacity-0 md:group-hover:opacity-100 focus:opacity-100"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between mt-8">
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={isScanning || !!activeTaskId}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:bg-slate-100 disabled:text-slate-400 transition-all shadow-sm shadow-indigo-100 active:scale-95"
          >
            <Play className={`h-4 w-4 ${isScanning ? 'animate-pulse' : ''}`} />
            {activeTaskId ? 'Running...' : 'Scan Now'}
          </button>
          
          <Link
            href={`/topics/${topic.id}/briefs`}
            className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-600 rounded-xl text-sm font-bold hover:bg-slate-50 transition-all"
          >
            <History className="h-4 w-4" />
            History
          </Link>
        </div>

        <ScanStatusBadge 
          taskId={activeTaskId} 
          onFinished={() => setActiveTaskId(null)} 
        />
      </div>

      <Link
        href={`/topics/${topic.id}`}
        className="absolute top-4 right-4 p-2 text-slate-300 hover:text-indigo-600 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
      >
        <ExternalLink className="h-4 w-4" />
      </Link>
    </div>
  );
}
