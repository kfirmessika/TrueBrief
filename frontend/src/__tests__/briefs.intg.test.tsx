import { describe, it, expect, vi } from "vitest";
import { screen, render } from "@testing-library/react";
import BriefHistoryPage from "@/app/topics/[id]/briefs/page.tsx";
import BriefDetailPage from "@/app/topics/[id]/briefs/[briefId]/page.tsx";
import { server } from "../test/server";
import { http, HttpResponse } from "msw";

const API_URL = "http://localhost:8000/api/v1";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  notFound: vi.fn(),
}));

// Mock Clerk auth since apiFetch uses it
vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({
    getToken: () => Promise.resolve("mock-token"),
  }),
}));

describe("Briefs Integration (MSW)", () => {
  const mockParams = { id: "topic-1", briefId: "brief-1" };

  it("Happy path: fetches and renders brief content", async () => {
    const mockBrief = {
      id: "brief-1",
      topic_id: "topic-1",
      content: "## The Intelligence\nEverything is looking good.",
      delivered_at: "2026-05-11T00:00:00Z",
    };

    const mockTopic = {
      id: "topic-1",
      raw_query: "Global Warming",
    };

    server.use(
      http.get(`${API_URL}/briefs/brief-1`, () => HttpResponse.json(mockBrief)),
      http.get(`${API_URL}/topics/topic-1`, () => HttpResponse.json(mockTopic))
    );

    // Since these are RSCs (async components), we await the result of the function call
    // then render the returned JSX.
    const Page = await BriefDetailPage({ params: mockParams });
    render(Page);

    // Verify topic title
    expect(screen.getByText("Global Warming")).toBeInTheDocument();
    
    // Verify markdown rendering
    const heading = screen.getByText("The Intelligence");
    expect(heading.tagName).toBe("H3"); // h2 -> h3 mapping in BriefContent
    expect(screen.getByText("Everything is looking good.")).toBeInTheDocument();
    
    // Verify date formatting
    expect(screen.getByText(/May 11, 2026/i)).toBeInTheDocument();
  });

  it("404 brief: calls notFound()", async () => {
    server.use(
      http.get(`${API_URL}/briefs/brief-1`, () => new HttpResponse(null, { status: 404 })),
      http.get(`${API_URL}/topics/topic-1`, () => HttpResponse.json({ id: 'topic-1' }))
    );

    const { notFound } = await import("next/navigation");
    
    try {
      await BriefDetailPage({ params: mockParams });
    } catch (e) {
      // In some test envs, notFound() might throw or just be called
    }

    expect(notFound).toHaveBeenCalled();
  });

  it("Empty history: shows empty state message", async () => {
    server.use(
      http.get(`${API_URL}/topics/topic-1/briefs`, () => HttpResponse.json([]))
    );

    const Page = await BriefHistoryPage({ params: { id: "topic-1" } });
    render(Page);

    expect(screen.getByText(/no briefs yet/i)).toBeInTheDocument();
    expect(screen.getByText(/trigger a manual scan to get started/i)).toBeInTheDocument();
  });
});
