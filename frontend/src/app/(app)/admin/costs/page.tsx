'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Database, Server } from 'lucide-react';
import { useState } from 'react';
import { useApi } from '@/lib/useApi';

interface Bucket { provider?: string; stage?: string; cost_usd: number; calls: number; tokens: number; }
interface CostResponse {
  telemetry_ready: boolean; message?: string; days: number;
  summary: { cost_usd: number; calls: number; tokens: number; average_cost_per_day_usd: number; average_cost_per_call_usd: number; } | null;
  daily: Array<{ date: string; cost_usd: number; calls: number; tokens: number; }>;
  by_provider: Bucket[]; by_stage: Bucket[];
  credits: Array<{ provider: string; monthly_credit_usd: number; estimated_used_usd: number; estimated_remaining_usd: number; }>;
  cost_note?: string;
}
const WINDOWS = [{ label: 'Today', days: 1 }, { label: '7 days', days: 7 }, { label: '30 days', days: 30 }, { label: 'All history', days: 0 }];
const usd = (n: number) => `$${n.toFixed(n < 0.01 ? 5 : 2)}`;

export default function AdminCostsPage() {
  const api = useApi();
  const [days, setDays] = useState(30);
  const { data, isLoading, isError } = useQuery<CostResponse>({
    queryKey: ['admin-costs', days], queryFn: async () => (await api.get('/admin/costs', { params: { days } })).data,
    staleTime: 30_000, retry: 0,
  });
  if (isLoading) return <div style={{ padding: 32 }}>Loading costs…</div>;
  if (isError || !data) return <div style={{ padding: 32, color: '#DC2626' }}><AlertCircle size={16} /> Could not load costs.</div>;
  if (!data.telemetry_ready) return <div style={{ maxWidth: 900, margin: '0 auto', padding: 32 }}><h1>Costs</h1><div style={warningStyle}><AlertCircle size={17} /> {data.message}</div></div>;
  const summary = data.summary!;
  return <div style={{ maxWidth: 1120, margin: '0 auto', padding: '32px 24px' }}>
    <h1 style={{ margin: 0, fontSize: 21 }}>Costs and usage</h1>
    <p style={{ margin: '5px 0 16px', fontSize: 13, color: 'var(--color-text-tertiary)' }}>Change the window, then keep scrolling for the complete daily history in that window.</p>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>{WINDOWS.map(option => <button key={option.days} onClick={() => setDays(option.days)} style={{ ...tabStyle, ...(days === option.days ? activeTabStyle : {}) }}>{option.label}</button>)}</div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, marginBottom: 22 }}>
      <Metric label="Recorded cost" value={usd(summary.cost_usd)} /><Metric label="Successful calls" value={summary.calls.toLocaleString()} /><Metric label="Average / day" value={usd(summary.average_cost_per_day_usd)} /><Metric label="Average / call" value={usd(summary.average_cost_per_call_usd)} />
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <Breakdown title="By provider" rows={data.by_provider} field="provider" /><Breakdown title="By pipeline stage" rows={data.by_stage} field="stage" />
    </div>
    <h2 style={sectionTitle}>Monthly free-credit estimates</h2>
    <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>Based only on successful calls recorded by TrueBrief this calendar month. Other apps using the same provider key are not visible.</p>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12 }}>{data.credits.map(credit => <div key={credit.provider} style={cardStyle}><strong style={{ textTransform: 'capitalize' }}>{credit.provider}</strong><p style={{ fontSize: 13 }}>{usd(credit.estimated_remaining_usd)} estimated remaining of {usd(credit.monthly_credit_usd)}</p><small>TrueBrief usage: {usd(credit.estimated_used_usd)}</small></div>)}</div>
    <h2 style={sectionTitle}>Daily history</h2>
    <div style={{ ...cardStyle, maxHeight: 520, overflowY: 'auto' }}>{data.daily.map(day => <div key={day.date} style={rowStyle}><span>{day.date}</span><span>{day.calls.toLocaleString()} calls · {day.tokens.toLocaleString()} tokens</span><strong>{usd(day.cost_usd)}</strong></div>)}{data.daily.length === 0 && <p style={{ color: 'var(--color-text-tertiary)' }}>No recorded calls in this window.</p>}</div>
    <div style={{ ...warningStyle, marginTop: 18 }}><Database size={16} /> {data.cost_note}</div>
    <div style={{ ...cardStyle, marginTop: 12, display: 'flex', gap: 10, alignItems: 'flex-start' }}><Server size={18} /><div><strong>Railway infrastructure</strong><p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>Railway CPU, RAM, network and storage are not included in API-call totals. The service exposes this through its workspace usage API; connect a scoped Railway token before showing an actual infrastructure total rather than estimating one from application calls.</p></div></div>
  </div>;
}
function Metric({ label, value }: { label: string; value: string }) { return <div style={cardStyle}><div style={{ color: 'var(--color-text-tertiary)', fontSize: 11 }}>{label}</div><strong style={{ fontSize: 20, display: 'block', marginTop: 6 }}>{value}</strong></div>; }
function Breakdown({ title, rows, field }: { title: string; rows: Bucket[]; field: 'provider' | 'stage' }) { return <section style={cardStyle}><h2 style={{ margin: '0 0 8px', fontSize: 14 }}>{title}</h2>{rows.map(row => <div key={row[field]} style={rowStyle}><span>{row[field]}</span><span>{row.calls.toLocaleString()} calls</span><strong>{usd(row.cost_usd)}</strong></div>)}</section>; }
const cardStyle: React.CSSProperties = { padding: 14, border: '0.5px solid var(--color-border-secondary)', borderRadius: 10, background: 'var(--color-background-secondary)' };
const rowStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 12, alignItems: 'center', padding: '9px 0', borderTop: '0.5px solid var(--color-border-tertiary)', fontSize: 12 };
const sectionTitle: React.CSSProperties = { margin: '28px 0 8px', fontSize: 15 };
const tabStyle: React.CSSProperties = { border: '0.5px solid var(--color-border-secondary)', borderRadius: 20, padding: '6px 11px', background: 'var(--color-background-secondary)', color: 'var(--color-text-secondary)', cursor: 'pointer', fontSize: 12, fontFamily: 'inherit' };
const activeTabStyle: React.CSSProperties = { background: 'var(--tb-green-light)', color: 'var(--tb-green-dark)', borderColor: 'var(--tb-green-border)' };
const warningStyle: React.CSSProperties = { display: 'flex', gap: 8, alignItems: 'center', padding: 13, borderRadius: 9, background: '#FFFBEB', color: '#78350F', fontSize: 12 };
