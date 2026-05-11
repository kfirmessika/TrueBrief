import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import HistoryPage from "@/app/history/page";
import { server } from "../test/server";
import { http, HttpResponse } from "msw";

const API_URL = "http://localhost:8000/api/v1";

// Mock Clerk auth since apiFetch uses it
vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({
    getToken: () => Promise.resolve("mock-token"),
  }),
}));

describe("History Page (Integration)", () => {
  it("renders empty state when user has no briefs", async () => {
    server.use(
      http.get(`${API_URL}/briefs/history`, () => HttpResponse.json([]))
    );

    const Page = await HistoryPage();
    render(Page);

    expect(screen.getByText(/no briefs yet/i)).toBeInTheDocument();
    expect(screen.getByText(/add a topic to get started/i)).toBeInTheDocument();
  });

  it("renders brief cards grouped by topic name", async () => {
    const mockHistory = [
      {
        topic_id: "topic-1",
        topic_name: "AI News",
        brief_id: "brief-1",
        created_at: "2026-05-08T10:00:00Z",
        summary_preview: "AI developments are accelerating rapidly",
      },
      {
        topic_id: "topic-2",
        topic_name: "Tech Markets",
        brief_id: "brief-2",
        created_at: "2026-05-07T10:00:00Z",
        summary_preview: "Market trends show steady growth",
      },
    ];

    server.use(
      http.get(`${API_URL}/briefs/history`, () => HttpResponse.json(mockHistory))
    );

    const Page = await HistoryPage();
    render(Page);

    expect(screen.getByText("AI News")).toBeInTheDocument();
    expect(screen.getByText("Tech Markets")).toBeInTheDocument();
    expect(screen.getByText(/AI developments are accelerating rapidly/)).toBeInTheDocument();
    expect(screen.getByText(/Market trends show steady growth/)).toBeInTheDocument();
  });

  it("renders multiple briefs under the same topic section", async () => {
    const mockHistory = [
      {
        topic_id: "topic-1",
        topic_name: "AI News",
        brief_id: "brief-1",
        created_at: "2026-05-08T10:00:00Z",
        summary_preview: "First brief content",
      },
      {
        topic_id: "topic-1",
        topic_name: "AI News",
        brief_id: "brief-2",
        created_at: "2026-05-07T10:00:00Z",
        summary_preview: "Second brief content",
      },
    ];

    server.use(
      http.get(`${API_URL}/briefs/history`, () => HttpResponse.json(mockHistory))
    );

    const Page = await HistoryPage();
    render(Page);

    // Only one heading for AI News (topic grouped once)
    const headings = screen.getAllByText("AI News");
    expect(headings).toHaveLength(1);

    // Both brief previews visible
    expect(screen.getByText(/First brief content/)).toBeInTheDocument();
    expect(screen.getByText(/Second brief content/)).toBeInTheDocument();
  });

  it("brief cards link to the correct brief detail page", async () => {
    const mockHistory = [
      {
        topic_id: "topic-1",
        topic_name: "AI News",
        brief_id: "brief-abc",
        created_at: "2026-05-08T10:00:00Z",
        summary_preview: "Some preview text",
      },
    ];

    server.use(
      http.get(`${API_URL}/briefs/history`, () => HttpResponse.json(mockHistory))
    );

    const Page = await HistoryPage();
    render(Page);

    const link = screen.getByRole("link", { name: /some preview text/i });
    expect(link).toHaveAttribute("href", "/topics/topic-1/briefs/brief-abc");
  });

  it("throws error when API call fails", async () => {
    server.use(
      http.get(`${API_URL}/briefs/history`, () => new HttpResponse(null, { status: 500 }))
    );

    await expect(HistoryPage()).rejects.toThrow("Failed to load brief history");
  });
});
