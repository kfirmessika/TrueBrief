import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import DashboardClient from '@/app/dashboard/DashboardClient';
import { renderWithProviders } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8000/api/v1';

describe('Topic Management Integration (MSW)', () => {
  it('Add topic → appears in list within 1s (optimistic)', async () => {
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([])),
      http.get(`${API_URL}/billing/status`, () => HttpResponse.json({
        tier: 'free', limits: { max_topics: 2 }
      }))
    );

    renderWithProviders(<DashboardClient initialTopics={[]} initialBilling={null} />);
    
    const input = await screen.findByPlaceholderText(/track a new topic/i);
    fireEvent.change(input, { target: { value: 'New World Order' } });
    
    const btn = screen.getByRole('button', { name: /add topic/i });
    
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([
        { id: 'topic-new', raw_query: 'New World Order', frequency: 'hourly', is_active: true, last_scan_at: null }
      ]))
    );

    fireEvent.click(btn);
    
    await screen.findByText('New World Order', {}, { timeout: 3000 });
  });

  it('Add 3rd topic on Free tier → shows upgrade banner', async () => {
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([
        { id: 't1', raw_query: 'T1', frequency: 'h', is_active: true },
        { id: 't2', raw_query: 'T2', frequency: 'h', is_active: true }
      ])),
      http.get(`${API_URL}/billing/status`, () => HttpResponse.json({
        tier: 'free', limits: { max_topics: 2 }
      }))
    );

    renderWithProviders(<DashboardClient initialTopics={[]} initialBilling={null} />);
    
    const banner = await screen.findByText(/limit reached/i);
    expect(banner).toBeInTheDocument();
  });

  it('Delete topic → row disappears', async () => {
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([
        { id: 'topic-1', raw_query: 'AI Safety', frequency: 'h', is_active: true }
      ]))
    );

    renderWithProviders(<DashboardClient initialTopics={[]} initialBilling={null} />);
    
    const deleteBtn = await screen.findByLabelText('Delete Topic');
    fireEvent.click(deleteBtn);

    const confirmBtn = screen.getByRole('button', { name: /delete everything/i });
    
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([]))
    );

    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByText('AI Safety')).not.toBeInTheDocument();
      expect(screen.getByText(/no topics yet/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('Trigger scan → badge cycles through states', async () => {
    server.use(
      http.get(`${API_URL}/topics`, () => HttpResponse.json([
        { id: 'topic-1', raw_query: 'AI Safety', frequency: 'h', is_active: true }
      ])),
      http.get(`${API_URL}/billing/status`, () => HttpResponse.json({
        tier: 'free', limits: { max_topics: 2 }
      }))
    );

    renderWithProviders(<DashboardClient initialTopics={[]} initialBilling={null} />);
    
    const scanBtn = await screen.findByRole('button', { name: /scan now/i });
    
    // Initial scan trigger
    server.use(
      http.post(`${API_URL}/topics/topic-1/scan`, () => HttpResponse.json({ task_id: 'task-123' })),
      http.get(`${API_URL}/scan-status/task-123`, () => HttpResponse.json({ state: 'PENDING' }))
    );

    fireEvent.click(scanBtn);

    // 1. Verify Queued
    await screen.findByText(/queued/i, {}, { timeout: 3000 });

    // 2. Transition to STARTED
    server.use(
      http.get(`${API_URL}/scan-status/task-123`, () => HttpResponse.json({ state: 'STARTED' }))
    );
    await screen.findByText(/running/i, {}, { timeout: 5000 }); // Wait for polling

    // 3. Transition to SUCCESS
    server.use(
      http.get(`${API_URL}/scan-status/task-123`, () => HttpResponse.json({ state: 'SUCCESS' }))
    );
    await screen.findByText(/complete/i, {}, { timeout: 5000 }); // Wait for polling
  });
});
