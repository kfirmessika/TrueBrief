import Sidebar from '@/components/layout/Sidebar';
import BottomTabBar from '@/components/layout/BottomTabBar';

/**
 * App shell. Two layouts, one tree — switched purely in CSS (globals.css) so
 * there is no hydration flash and no viewport measuring on the server:
 *   ≥768px  → row:    [ Sidebar | main ]
 *   <768px  → column: [ main / BottomTabBar ]
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="tb-app-shell">
      <div className="tb-sidebar-wrap">
        <Sidebar />
      </div>

      <main className="tb-app-main">
        {children}
      </main>

      <BottomTabBar />
    </div>
  );
}
