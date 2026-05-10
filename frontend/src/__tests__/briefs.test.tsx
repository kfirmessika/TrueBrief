import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import BriefContent from "@/components/briefs/BriefContent";
import BriefCard from "@/components/briefs/BriefCard";
import CopyLinkButton from "@/components/briefs/CopyLinkButton";
import { renderWithProviders } from "../test/utils";

describe("Brief Display Components (Unit)", () => {
  describe("BriefContent", () => {
    it("renders plain paragraph text", () => {
      renderWithProviders(<BriefContent content="Hello world" />);
      expect(screen.getByText("Hello world")).toBeInTheDocument();
    });

    it("renders ## heading as styled heading element", () => {
      renderWithProviders(<BriefContent content="## My Heading" />);
      const heading = screen.getByRole("heading", { level: 3 });
      expect(heading).toHaveTextContent("My Heading");
      expect(heading).toHaveClass("text-xl");
    });

    it("renders **bold** as strong", () => {
      renderWithProviders(<BriefContent content="This is **bold**" />);
      const strong = screen.getByText("bold");
      expect(strong.tagName).toBe("STRONG");
      expect(strong).toHaveClass("font-black");
    });

    it("renders [link](url) with indigo class", () => {
      renderWithProviders(<BriefContent content="[My Link](https://example.com)" />);
      const link = screen.getByRole("link", { name: "My Link" });
      expect(link).toHaveAttribute("href", "https://example.com");
      expect(link).toHaveClass("text-indigo-600");
    });
  });

  describe("BriefCard", () => {
    const mockBrief = {
      id: "brief-1",
      topic_id: "topic-1",
      content: "# Title\nThis is **markdown** content `code`.",
      delivered_at: new Date().toISOString(),
    };

    it("renders delivery date in human-readable format", () => {
      renderWithProviders(<BriefCard brief={mockBrief} topicId="topic-1" />);
      expect(screen.getByText(/less than a minute ago/i)).toBeInTheDocument();
    });

    it("strips markdown symbols from preview text", () => {
      renderWithProviders(<BriefCard brief={mockBrief} topicId="topic-1" />);
      // Should see "Title This is markdown content code" (symbols removed)
      expect(screen.getByText(/Title This is markdown content code/i)).toBeInTheDocument();
    });

    it("has correct href linking to detail page", () => {
      renderWithProviders(<BriefCard brief={mockBrief} topicId="topic-1" />);
      const link = screen.getByRole("link", { name: /read full brief/i });
      expect(link).toHaveAttribute("href", "/topics/topic-1/briefs/brief-1");
    });
  });

  describe("CopyLinkButton", () => {
    beforeEach(() => {
      // Mock clipboard API
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });
      
      // Mock window.location
      vi.stubGlobal('location', { href: 'http://localhost:3000/test' });
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("shows 'Copied!' text after click", async () => {
      renderWithProviders(<CopyLinkButton />);
      const button = screen.getByRole("button", { name: /copy link/i });
      
      fireEvent.click(button);
      
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost:3000/test');
      
      await waitFor(() => {
        expect(screen.getByText(/copied!/i)).toBeInTheDocument();
      });
      
      // Check for green class
      expect(button).toHaveClass("bg-green-500");
    });
  });
});
