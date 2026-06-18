import { describe, it, expect, vi, Mock } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { TopicCard } from '@/components/topics/TopicCard';
import { AddTopicForm } from '@/components/topics/AddTopicForm';
import { UpgradeBanner } from '@/components/topics/UpgradeBanner';
import { ScanStatusBadge } from '@/components/topics/ScanStatusBadge';
import { renderWithProviders } from '../test/utils';
import { useScanStatus } from '@/hooks/useTopics';

// Mock hooks
vi.mock('@/hooks/useTopics', () => ({
  useScanStatus: vi.fn(),
}));

describe('Topic Management UI Components', () => {
  const mockTopic = {
    id: 'topic-1',
    raw_query: 'AI Safety',
    frequency: 'hourly',
    is_active: true,
    last_scan_at: new Date(Date.now() - 3600000).toISOString(), // 1h ago
  };

  describe('TopicCard', () => {
    it('renders raw_query and humanized last_scan_at', () => {
      (useScanStatus as Mock).mockReturnValue({ data: { state: 'PENDING' }, isLoading: false });
      renderWithProviders(
        <TopicCard topic={mockTopic} onScan={async () => 'task-123'} onDelete={() => {}} />
      );
      expect(screen.getByText('AI Safety')).toBeInTheDocument();
      expect(screen.getByText(/about 1 hour ago/i)).toBeInTheDocument();
    });

    it('fires onScan when Scan Now clicked', async () => {
      (useScanStatus as Mock).mockReturnValue({ data: { state: 'PENDING' }, isLoading: false });
      const onScan = vi.fn().mockResolvedValue('task-123');
      renderWithProviders(
        <TopicCard topic={mockTopic} onScan={onScan} onDelete={() => {}} />
      );
      
      const scanBtn = screen.getByRole('button', { name: /scan now/i });
      fireEvent.click(scanBtn);
      
      await waitFor(() => {
        expect(onScan).toHaveBeenCalledWith('topic-1');
      });
    });

    it('fires onDelete when Delete clicked in the options menu', () => {
      (useScanStatus as Mock).mockReturnValue({ data: { state: 'PENDING' }, isLoading: false });
      const onDelete = vi.fn();
      renderWithProviders(
        <TopicCard topic={mockTopic} onScan={async () => 'task-123'} onDelete={onDelete} />
      );

      // Delete lives behind the three-dot menu now — open it first.
      fireEvent.click(screen.getByRole('button', { name: /topic options/i }));
      fireEvent.click(screen.getByRole('button', { name: /delete/i }));
      expect(onDelete).toHaveBeenCalledWith('topic-1');
    });
  });

  describe('AddTopicForm', () => {
    it('disables submit when input is empty', () => {
      renderWithProviders(<AddTopicForm onSubmit={async () => {}} isLoading={false} />);
      const btn = screen.getByRole('button', { name: /add topic/i });
      expect(btn).toBeDisabled();
    });

    it('calls onSubmit with trimmed query', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      renderWithProviders(<AddTopicForm onSubmit={onSubmit} isLoading={false} />);
      
      const input = screen.getByPlaceholderText(/track a new topic/i);
      fireEvent.change(input, { target: { value: '  Tesla News  ' } });
      
      const btn = screen.getByRole('button', { name: /add topic/i });
      fireEvent.click(btn);
      
      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith('Tesla News');
      });
    });
  });

  describe('UpgradeBanner', () => {
    it('renders correctly with limit info', () => {
      renderWithProviders(<UpgradeBanner currentCount={2} maxTopics={2} />);
      expect(screen.getByText(/you're using 2 of 2 free topics/i)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /upgrade now/i })).toBeInTheDocument();
    });
  });

  describe('ScanStatusBadge', () => {
    it('renders Queued state when pending', () => {
      (useScanStatus as Mock).mockReturnValue({ data: { state: 'PENDING' }, isLoading: false });
      renderWithProviders(<ScanStatusBadge taskId="task-123" />);
      expect(screen.getByText(/queued/i)).toBeInTheDocument();
    });

    it('renders Complete state when success', () => {
      (useScanStatus as Mock).mockReturnValue({ data: { state: 'SUCCESS' }, isLoading: false });
      renderWithProviders(<ScanStatusBadge taskId="task-123" />);
      expect(screen.getByText(/complete/i)).toBeInTheDocument();
    });
  });
});
