import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8000/api/v1';

export const handlers = [
  // List topics
  http.get(`${API_URL}/topics`, () => {
    return HttpResponse.json([
      { id: 'topic-1', raw_query: 'AI Safety', frequency: 'hourly', is_active: true, last_scan_at: null },
      { id: 'topic-2', raw_query: 'Tesla Bot', frequency: 'hourly', is_active: true, last_scan_at: null },
    ]);
  }),

  // Create topic
  http.post(`${API_URL}/topics`, async ({ request }) => {
    const body: any = await request.json();
    
    // Simulate 402 if query is 'PRO_TOPIC' (test case)
    if (body.raw_query === 'PRO_TOPIC') {
      return new HttpResponse(
        JSON.stringify({ detail: 'Upgrade your plan to add more topics' }), 
        { status: 402 }
      );
    }

    return HttpResponse.json({
      id: 'topic-new',
      raw_query: body.raw_query,
      frequency: 'hourly',
      is_active: true,
      last_scan_at: null
    });
  }),

  // Delete topic
  http.delete(`${API_URL}/topics/:id`, () => {
    return HttpResponse.json({ status: 'deleted' });
  }),

  // Trigger scan
  http.post(`${API_URL}/topics/:id/scan`, () => {
    return HttpResponse.json({ task_id: 'task-123', topic_id: 'topic-1', status: 'queued' });
  }),

  // Scan status
  http.get(`${API_URL}/scan-status/:taskId`, ({ params }) => {
    const { taskId } = params;
    // Simulate progression logic can be handled in the test itself by overriding the handler
    return HttpResponse.json({ task_id: taskId, state: 'SUCCESS', result: { status: 'ok' } });
  }),

  // Billing status
  http.get(`${API_URL}/billing/status`, () => {
    return HttpResponse.json({
      user_id: 'user_123',
      tier: 'free',
      status: 'active',
      stripe_customer_id: null,
      current_period_end: null,
      limits: {
        max_topics: 2,
        min_interval_hours: 24,
        sources: ['google_news'],
        private_topics: false,
      }
    });
  }),
];
