'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, CircleDashed, ExternalLink } from 'lucide-react';
import { useApi } from '@/lib/useApi';

interface Observed { provider: string; model: string; at: string; duration_ms: number | null; cost_usd: number; }
interface Service {
  stage: string; label: string; description: string; configured_provider: string; configured_model: string;
  credentials_configured: boolean; fallback_order: string[]; last_observed: Observed | null; provider_usage_source: string;
}
interface ServiceResponse { services: Service[]; topic_search: { label: string; provider: string; model: string; description: string; }; }

export default function AdminServicesPage() {
  const api = useApi();
  const { data, isLoading, isError } = useQuery<ServiceResponse>({
    queryKey: ['admin-services'], queryFn: async () => (await api.get('/admin/services')).data,
    staleTime: 20_000, refetchInterval: 30_000, retry: 0,
  });
  if (isLoading) return <div style={{ padding: 32 }}>Loading service map…</div>;
  if (isError || !data) return <div style={{ padding: 32, color: '#DC2626' }}><AlertCircle size={16} /> Could not load services.</div>;

  return (
    <div style={{ maxWidth: 1120, margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ margin: 0, fontSize: 21 }}>V5 services</h1>
      <p style={{ margin: '5px 0 22px', fontSize: 13, color: 'var(--color-text-tertiary)' }}>
        Shows the deployed route and the most recently observed successful route. A fallback can differ from the configured service during an outage.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: 12 }}>
        {data.services.map(service => <ServiceCard key={service.stage} service={service} />)}
        <article style={cardStyle}>
          <div style={eyebrow}>Separate search index</div>
          <h2 style={titleStyle}>{data.topic_search.label}</h2>
          <p style={copyStyle}>{data.topic_search.description}</p>
          <div style={routeStyle}>{data.topic_search.provider} · {data.topic_search.model}</div>
          <p style={{ ...copyStyle, marginTop: 12 }}>This stays local so autocomplete is fast and never consumes your pipeline embedding quota.</p>
        </article>
      </div>
      <div style={{ marginTop: 20, padding: 14, borderRadius: 10, background: '#FFFBEB', color: '#78350F', fontSize: 12 }}>
        <strong>Provider balance:</strong> no provider balance is guessed here. Gemini’s active limits are visible in AI Studio; Linkup and Brave credit estimates live on the Costs page and use only successful TrueBrief calls.
        <a href="https://aistudio.google.com/" target="_blank" rel="noreferrer" style={{ marginLeft: 8, color: 'inherit' }}>Open AI Studio <ExternalLink size={11} style={{ verticalAlign: 'middle' }} /></a>
      </div>
    </div>
  );
}

function ServiceCard({ service }: { service: Service }) {
  const healthy = service.credentials_configured;
  return <article style={cardStyle}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      {healthy ? <CheckCircle2 size={15} color="#16A34A" /> : <AlertCircle size={15} color="#DC2626" />}
      <span style={eyebrow}>{service.stage}</span>
      <span style={{ marginLeft: 'auto', fontSize: 11, color: healthy ? '#15803D' : '#B91C1C' }}>{healthy ? 'credentials set' : 'credentials missing'}</span>
    </div>
    <h2 style={titleStyle}>{service.label}</h2>
    <p style={copyStyle}>{service.description}</p>
    <div style={routeStyle}>Configured: <strong>{service.configured_provider}</strong> · {service.configured_model}</div>
    {service.fallback_order.length > 0 && <p style={{ ...copyStyle, marginTop: 9 }}>Fallbacks: {service.fallback_order.join(' → ')}</p>}
    <div style={{ borderTop: '0.5px solid var(--color-border-tertiary)', marginTop: 12, paddingTop: 10, fontSize: 12 }}>
      {service.last_observed ? <><CircleDashed size={12} style={{ verticalAlign: 'middle' }} /> Last used {service.last_observed.provider} · {new Date(service.last_observed.at).toLocaleString()}</> : 'No successful call recorded yet.'}
    </div>
  </article>;
}

const cardStyle: React.CSSProperties = { padding: 16, border: '0.5px solid var(--color-border-secondary)', borderRadius: 12, background: 'var(--color-background-secondary)' };
const eyebrow: React.CSSProperties = { fontSize: 11, fontWeight: 700, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' };
const titleStyle: React.CSSProperties = { fontSize: 15, margin: '8px 0 4px', color: 'var(--color-text-primary)' };
const copyStyle: React.CSSProperties = { fontSize: 12, lineHeight: 1.45, margin: 0, color: 'var(--color-text-secondary)' };
const routeStyle: React.CSSProperties = { marginTop: 12, padding: '7px 9px', borderRadius: 7, background: 'var(--color-background-tertiary)', fontSize: 12, overflowWrap: 'anywhere' };
