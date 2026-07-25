import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import BriefContent from "@/components/briefs/BriefContent";
import { renderWithProviders } from "../test/utils";

// BriefCard and CopyLinkButton were removed as orphaned V4-era components (no route
// ever rendered them — the topic page shows the alpha+context timeline directly).
// BriefContent survives because admin/compare/page.tsx still uses it to render raw
// brief markdown for the internal V4/V5/reference comparison tool.
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
    });

    it("renders [link](url) as an anchor to the url", () => {
      renderWithProviders(<BriefContent content="[My Link](https://example.com)" />);
      const link = screen.getByRole("link", { name: "My Link" });
      expect(link).toHaveAttribute("href", "https://example.com");
    });
  });
});
