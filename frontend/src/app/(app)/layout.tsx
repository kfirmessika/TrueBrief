import Sidebar from '@/components/layout/Sidebar';
import BottomTabBar from '@/components/layout/BottomTabBar';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

/**
 * App shell. Two layouts, one tree — switched purely in CSS (globals.css) so
 * there is no hydration flash and no viewport measuring on the server:
 *   ≥768px  → row:    [ Sidebar | main ]
 *   <768px  → column: [ main / BottomTabBar ]
 *
 * The routed content is wrapped in ErrorBoundary (not the whole shell) so a
 * render error on one page shows a recoverable card in `main` while Sidebar/
 * BottomTabBar stay mounted and usable to navigate away from it.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="tb-app-shell">
      <div className="tb-sidebar-wrap">
        <Sidebar />
      </div>

      <main className="tb-app-main">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>

      <BottomTabBar />
    </div>
  );
}
