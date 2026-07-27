import { describe, it, expect } from "vitest";
import { parseBrief } from "@/app/(app)/topics/[id]/page";

// Verbatim excerpt of a REAL stored brief (briefs table, topic "iran war",
// delivered 2026-07-26T03:59Z) — not a hand-written fixture. If the Briefer prompt
// in src/truebrief/llm/prompts.py changes shape, this test should fail loudly
// rather than the panel silently rendering nothing.
const REAL_BRIEF = `📋 TrueBrief | Iran War | July 26, 2026

**📌 Bottom line:** The US President has directed the military to halt new strikes on Iran, ending a nearly two-week period of consecutive US nighttime attacks against the country.

🆕 NEW STORIES (7)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Escalating Conflict**
• The Iranian Islamic Revolutionary Guard Corps issued a warning for civilians to maintain a distance of at least 500 meters from US military personnel. → Sources: [kyivpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEi8k5h)
• US forces conducted strikes against Iranian military targets in Khuzestan and Gilan provinces. → Sources: [kyivpost.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEi8k5h), [reuters.com](https://example.com/r)

📈 UPDATES (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━
**Diplomacy**
• Mediators from Qatar and Pakistan reported progress.`;

describe("parseBrief", () => {
  const blocks = parseBrief(REAL_BRIEF);

  it("drops the 📋 header and ━━━ rules", () => {
    expect(blocks.some((b) => "text" in b && b.text.includes("📋"))).toBe(false);
    expect(blocks.some((b) => "text" in b && /━/.test(b.text))).toBe(false);
  });

  it("extracts the bottom line as a lede", () => {
    const lede = blocks.find((b) => b.kind === "lede");
    expect(lede).toBeDefined();
    expect(lede && "text" in lede && lede.text).toMatch(/halt new strikes on Iran/);
    // the "**📌 Bottom line:**" label itself must not survive into the rendered text
    expect(lede && "text" in lede && lede.text).not.toMatch(/Bottom line/);
  });

  it("keeps both section badges", () => {
    const badges = blocks.filter((b) => b.kind === "badge");
    expect(badges).toHaveLength(2);
    expect(badges[0]).toHaveProperty("text", "🆕 NEW STORIES (7)");
    expect(badges[1]).toHaveProperty("text", "📈 UPDATES (1)");
  });

  it("unwraps **Section Title** markers", () => {
    const sections = blocks.filter((b) => b.kind === "section");
    expect(sections.map((s) => ("text" in s ? s.text : ""))).toEqual([
      "Escalating Conflict",
      "Diplomacy",
    ]);
  });

  it("splits bullet text from its source links", () => {
    const bullets = blocks.filter((b) => b.kind === "bullet");
    expect(bullets).toHaveLength(3);

    const first = bullets[0];
    if (first.kind !== "bullet") throw new Error("expected bullet");
    expect(first.bullet.text).toMatch(/at least 500 meters/);
    // the "→ Sources:" tail must be stripped out of the visible sentence
    expect(first.bullet.text).not.toMatch(/Sources:/);
    expect(first.bullet.sources).toEqual([
      { domain: "kyivpost.com", url: "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEi8k5h" },
    ]);
  });

  it("captures multiple sources on one bullet", () => {
    const bullets = blocks.filter((b) => b.kind === "bullet");
    const second = bullets[1];
    if (second.kind !== "bullet") throw new Error("expected bullet");
    expect(second.bullet.sources.map((s) => s.domain)).toEqual(["kyivpost.com", "reuters.com"]);
  });

  it("handles a bullet with no sources at all", () => {
    const bullets = blocks.filter((b) => b.kind === "bullet");
    const last = bullets[2];
    if (last.kind !== "bullet") throw new Error("expected bullet");
    expect(last.bullet.text).toBe("Mediators from Qatar and Pakistan reported progress.");
    expect(last.bullet.sources).toEqual([]);
  });

  it("returns nothing for an empty brief", () => {
    expect(parseBrief("")).toEqual([]);
  });
});
