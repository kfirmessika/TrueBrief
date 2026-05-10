import '@testing-library/jest-dom';
import { vi } from 'vitest';

import { server } from './server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock Clerk hooks globally for tests
vi.mock('@clerk/nextjs', () => ({
  useAuth: () => ({
    getToken: vi.fn(() => Promise.resolve('mock-token')),
    userId: 'user_123',
  }),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
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
