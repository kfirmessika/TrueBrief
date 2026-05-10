import { apiFetch } from "@/lib/api";
import DashboardClient from "./DashboardClient";

export const metadata = {
  title: "Dashboard | TrueBrief",
};

export default async function DashboardPage() {
  // Server-side pre-fetching for SSR speed and SEO
  const [topicsRes, billingRes] = await Promise.all([
    apiFetch("/topics"),
    apiFetch("/billing/status"),
  ]);

  const initialTopics = topicsRes.ok ? await topicsRes.json() : [];
  const initialBilling = billingRes.ok ? await billingRes.json() : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <DashboardClient 
        initialTopics={initialTopics} 
        initialBilling={initialBilling} 
      />
    </div>
  );
}
