'use client';

import axios, { AxiosInstance } from 'axios';
import { useAuth } from '@clerk/nextjs';
import { useMemo } from 'react';

const _raw = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_BASE_URL = _raw.endsWith('/api/v1') ? _raw : `${_raw.replace(/\/$/, '')}/api/v1`;

/**
 * Hook to get an Axios instance that automatically includes
 * the Clerk JWT in the Authorization header.
 * 
 * Use this in Client Components for data mutations and
 * client-side fetching via React Query.
 */
export function useApi(): AxiosInstance {
  const { getToken } = useAuth();

  return useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    instance.interceptors.request.use(async (config) => {
      try {
        const token = await getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.error('Failed to get auth token', error);
      }
      return config;
    });

    return instance;
  }, [getToken]);
}
