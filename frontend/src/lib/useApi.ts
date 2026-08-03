'use client';

import axios, { AxiosInstance } from 'axios';
import { useMemo } from 'react';
import { createClient } from './supabase/client';

const _raw = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_BASE_URL = _raw.endsWith('/api/v1') ? _raw : `${_raw.replace(/\/$/, '')}/api/v1`;

/**
 * Hook to get an Axios instance that automatically includes
 * the Supabase access token in the Authorization header.
 *
 * Use this in Client Components for data mutations and
 * client-side fetching via React Query.
 */
export function useApi(): AxiosInstance {
  return useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    instance.interceptors.request.use(async (config) => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.error('Failed to get auth token', error);
      }
      return config;
    });

    return instance;
  }, []);
}
