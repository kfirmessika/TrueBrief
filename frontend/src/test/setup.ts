import '@testing-library/jest-dom';
import { vi } from 'vitest';

import { server } from './server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock Supabase auth globally for tests
const mockSession = {
  access_token: 'mock-token',
  user: { id: 'user_123', email: 'test@example.com', user_metadata: {} },
};

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn(() => Promise.resolve({ data: { session: mockSession } })),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
      signOut: vi.fn(() => Promise.resolve({ error: null })),
      signInWithOAuth: vi.fn(() => Promise.resolve({ data: { url: null }, error: null })),
      signInWithOtp: vi.fn(() => Promise.resolve({ error: null })),
      exchangeCodeForSession: vi.fn(() => Promise.resolve({ error: null })),
    },
  }),
}));

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/',
  notFound: vi.fn(),
}));
