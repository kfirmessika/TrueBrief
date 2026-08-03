import axios from 'axios';

const _raw = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_BASE_URL = _raw.endsWith('/api/v1') ? _raw : `${_raw.replace(/\/$/, '')}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Topic Types
export interface Topic {
  id: string;
  raw_query: string;
  frequency: string;
  is_active: boolean;
  last_scan_at?: string | null;
  scan_started_at?: string | null;
  is_scanning?: boolean;
}

// Billing Types
export interface TierLimits {
  max_topics: number;
  min_interval_hours: number;
  sources: string[];
  private_topics: boolean;
  api_calls_per_day: number;
}

// API Key Types
export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyUsage {
  day: string;
  calls_used: number;
  daily_limit: number;
  tier: string;
}

export interface BillingStatus {
  user_id: string;
  tier: string;
  status: string;
  paddle_customer_id: string | null;
  current_period_end: number | null;
  limits: TierLimits;
}

// API Endpoints
export const topicsApi = {
  list: () => api.get<Topic[]>('/topics'),
  get: (id: string) => api.get<Topic>(`/topics/${id}`),
  create: (raw_query: string) => api.post<Topic>('/topics', { raw_query }),
  delete: (id: string) => api.delete(`/topics/${id}`),
  scan: (id: string) => api.post<{ task_id: string; topic_id: string; status: string }>(`/topics/${id}/scan`),
};

export const billingApi = {
  getStatus: () => api.get<BillingStatus>('/billing/status'),
};

// User Stats Types
export interface UserStats {
  total_briefs: number;
  articles_scanned: number;
  time_saved_minutes: number;
}

export const statsApi = {
  getStats: () => api.get<UserStats>('/users/me/stats'),
};

import { createClient } from "./supabase/server";

export async function apiFetch(path: string, init: RequestInit = {}) {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (session?.access_token) headers.set("Authorization", `Bearer ${session.access_token}`);
  headers.set("Content-Type", "application/json");
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}
