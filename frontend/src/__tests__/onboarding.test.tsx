import { describe, it, expect, vi, Mock } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/utils';
import OnboardingPage from '@/app/onboarding/page';
import { useTopics, useCreateTopic, useTriggerScan } from '@/hooks/useTopics';
import { useRouter } from 'next/navigation';

// Mock Clerk auth (not needed in unit tests — middleware handles it)
vi.mock('@clerk/nextjs', () => ({
  useAuth: () => ({ getToken: async () => 'test-token', isSignedIn: true }),
  useUser: () => ({ isLoaded: true, isSignedIn: true }),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

vi.mock('@/hooks/useTopics', () => ({
  useTopics: vi.fn(),
  useCreateTopic: vi.fn(),
  useTriggerScan: vi.fn(),
}));

const mockPush = vi.fn();
const mockReplace = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  (useRouter as Mock).mockReturnValue({ push: mockPush, replace: mockReplace });
  (useTriggerScan as Mock).mockReturnValue({ mutate: vi.fn() });
});

function setupTopicsMocks(opts: {
  topics?: any[];
  isLoading?: boolean;
  createFn?: () => Promise<any>;
}) {
  (useTopics as Mock).mockReturnValue({
    data: opts.topics ?? [],
    isLoading: opts.isLoading ?? false,
  });
  (useCreateTopic as Mock).mockReturnValue({
    mutateAsync: opts.createFn ?? vi.fn().mockResolvedValue({ id: 'new-topic-id' }),
    isPending: false,
  });
}

describe('OnboardingPage', () => {
  it('renders step 1 with topic input for a new user', () => {
    setupTopicsMocks({});
    renderWithProviders(<OnboardingPage />);
    expect(screen.getByText(/welcome to truebrief/i)).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/nvidia earnings/i)).toBeInTheDocument();
  });

  it('redirects to dashboard if user already has topics', () => {
    setupTopicsMocks({ topics: [{ id: 't1', raw_query: 'AI', frequency: 'hourly', is_active: true }] });
    renderWithProviders(<OnboardingPage />);
    expect(mockReplace).toHaveBeenCalledWith('/dashboard');
  });

  it('disables submit button when input is empty', () => {
    setupTopicsMocks({});
    renderWithProviders(<OnboardingPage />);
    const btn = screen.getByRole('button', { name: /build my first brief/i });
    expect(btn).toBeDisabled();
  });

  it('enables submit button when query is entered and moves to step 2', async () => {
    setupTopicsMocks({});
    renderWithProviders(<OnboardingPage />);
    const input = screen.getByPlaceholderText(/nvidia earnings/i);
    fireEvent.change(input, { target: { value: 'TSMC Chips' } });
    expect(screen.getByRole('button', { name: /build my first brief/i })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /build my first brief/i }));
    await waitFor(() => {
      expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument();
    });
  });

  it('moves to step 3 after successful topic creation', async () => {
    setupTopicsMocks({
      createFn: vi.fn().mockResolvedValue({ id: 'new-topic-id' }),
    });
    renderWithProviders(<OnboardingPage />);
    fireEvent.change(screen.getByPlaceholderText(/nvidia earnings/i), {
      target: { value: 'TSMC Chips' },
    });
    fireEvent.click(screen.getByRole('button', { name: /build my first brief/i }));
    await waitFor(() => {
      expect(screen.getByText(/pipeline live/i)).toBeInTheDocument();
      expect(screen.getByText(/step 3 of 3/i)).toBeInTheDocument();
    });
  });

  it('shows error and returns to step 1 if topic creation fails', async () => {
    setupTopicsMocks({
      createFn: vi.fn().mockRejectedValue({
        response: { data: { detail: 'Topic limit reached' } },
      }),
    });
    renderWithProviders(<OnboardingPage />);
    fireEvent.change(screen.getByPlaceholderText(/nvidia earnings/i), {
      target: { value: 'TSMC Chips' },
    });
    fireEvent.click(screen.getByRole('button', { name: /build my first brief/i }));
    await waitFor(() => {
      expect(screen.getByText(/topic limit reached/i)).toBeInTheDocument();
      expect(screen.getByText(/step 1 of 3/i)).toBeInTheDocument();
    });
  });

  it('"Skip and go to dashboard" navigates to /dashboard', () => {
    setupTopicsMocks({});
    renderWithProviders(<OnboardingPage />);
    fireEvent.click(screen.getByRole('button', { name: /skip and go to dashboard/i }));
    expect(mockPush).toHaveBeenCalledWith('/dashboard');
  });

  it('"Go to Dashboard" on step 3 navigates to /dashboard', async () => {
    setupTopicsMocks({
      createFn: vi.fn().mockResolvedValue({ id: 'new-topic-id' }),
    });
    renderWithProviders(<OnboardingPage />);
    fireEvent.change(screen.getByPlaceholderText(/nvidia earnings/i), {
      target: { value: 'TSMC Chips' },
    });
    fireEvent.click(screen.getByRole('button', { name: /build my first brief/i }));
    await waitFor(() => screen.getByText(/pipeline live/i));
    fireEvent.click(screen.getByRole('button', { name: /go to dashboard/i }));
    expect(mockPush).toHaveBeenCalledWith('/dashboard');
  });

  it('fills input when an example query pill is clicked', () => {
    setupTopicsMocks({});
    renderWithProviders(<OnboardingPage />);
    fireEvent.click(screen.getByRole('button', { name: 'NVIDIA Earnings' }));
    const input = screen.getByPlaceholderText(/nvidia earnings/i) as HTMLInputElement;
    expect(input.value).toBe('NVIDIA Earnings');
  });
});
