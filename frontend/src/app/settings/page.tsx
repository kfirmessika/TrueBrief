import { Metadata } from 'next';
import PushNotificationToggle from '@/components/PushNotificationToggle';

export const metadata: Metadata = {
  title: 'Settings | TrueBrief',
};

export default function SettingsPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="text-2xl font-bold text-slate-900 mb-8">Settings</h1>

      <section className="space-y-4">
        <h2 className="text-base font-semibold text-slate-500 uppercase tracking-wide">
          Notifications
        </h2>
        <PushNotificationToggle />
      </section>
    </div>
  );
}
