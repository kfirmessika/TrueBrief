#!/usr/bin/env python3
"""
scripts/dedup_quality_test.py

Runs the Alphas extracted in the v3 benchmark through the real dedup logic
(embedding + cosine + temporal adjustment + auto-merge thresholds) to see:

  1. How many Alphas survive per provider after dedup
  2. Which pairs get merged (and why)
  3. Whether Brave's higher volume is genuine diversity or redundancy

Uses the production embedding path (LLMClient.embed) and the production
threshold constants from arbiter.py. No DB writes — everything in-memory.

Usage:
    python scripts/dedup_quality_test.py
"""

from __future__ import annotations

import os, sys, datetime
from dataclasses import dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import numpy as np

# ── Production thresholds (from arbiter.py) ────────────────────────────────────
AUTO_MERGE_THRESHOLD  = 0.97   # auto-DUPLICATE, no LLM
GREY_ZONE_MIN         = 0.75   # below this = auto-NEW
SAME_DAY_DUP          = 0.93   # same date + same numbers → auto-DUPLICATE

TODAY = datetime.date.today().isoformat()

# ── Alpha data from the v3 benchmark run ──────────────────────────────────────
# Hardcoded from 2026-08-30_search-layer-v3-pipeline.md
# Format: (provider, topic, event_date, alpha_text, is_background)

RAW_ALPHAS = [
    # ── Iran US ceasefire ─────────────────────────────────────────────────────
    ("linkup", "Iran ceasefire", "2026-06-15", "The United States and Iran reached a two-week ceasefire agreement.", False),
    ("linkup", "Iran ceasefire", "2026-06-15", "President Trump announced the U.S.-Iran ceasefire agreement and the reopening of the Strait of Hormuz.", False),
    ("linkup", "Iran ceasefire", "2026-06-15", "Iranian Foreign Minister Abbas Araghchi confirmed that the reopening of the Strait of Hormuz would be coordinated with Iranian military forces.", False),
    ("linkup", "Iran ceasefire", "2026-06-14", "Iran blocked the Strait of Hormuz in response to weeks of U.S. and Israeli strikes.", True),
    ("linkup", "Iran ceasefire", "2026-08-30", "Iran reimposed restrictions on the Strait of Hormuz.", False),
    ("linkup", "Iran ceasefire", "2026-08-30", "Talks to finalize a longer-term agreement between the United States and Iran are scheduled to begin in Pakistan.", False),

    ("brave",  "Iran ceasefire", "2026-03-25", "Pakistani officials delivered a 15-point proposal from the United States to Iran detailing a ceasefire plan on March 25.", True),
    ("brave",  "Iran ceasefire", "2026-03-25", "Iran issued a 5-point counter-proposal responding to the United States ceasefire plan.", True),
    ("brave",  "Iran ceasefire", "2026-03-31", "Pakistan and China delivered a 5-point initiative for peace calling for an immediate end to all hostilities on March 31.", True),
    ("brave",  "Iran ceasefire", "2026-04-01", "Donald Trump stated on April 1 that Iran had asked the US for a ceasefire.", True),
    ("brave",  "Iran ceasefire", "2026-06-19", "Donald Trump announced a renewed ceasefire between Israel and Hezbollah on June 19.", True),
    ("brave",  "Iran ceasefire", "2026-06-20", "Iran declared that it closed the Strait of Hormuz again on June 20, citing Israeli strikes in southern Lebanon.", True),
    ("brave",  "Iran ceasefire", "2026-06-27", "The Joint Maritime Information Center announced a widened route through the Strait of Hormuz near Oman on June 27.", True),
    ("brave",  "Iran ceasefire", "2026-04-08", "The United States and Iran agreed to a ceasefire that included Israel between April 7 and April 8.", True),
    ("brave",  "Iran ceasefire", "2026-08-26", "Turkish news agency Anadolu reported on August 26 that the United States and Iran reached a ceasefire agreement including provisions for free navigation through the Strait of Hormuz.", False),
    ("brave",  "Iran ceasefire", "2026-08-26", "Iran's deputy foreign minister stated on August 26 that the Strait of Hormuz would not reopen until the United States changes its economic pressure.", False),
    ("brave",  "Iran ceasefire", "2026-08-25", "Two unclaimed projectile strikes disabled tankers off Oman near the Strait of Hormuz between August 24 and August 25.", False),
    ("brave",  "Iran ceasefire", "2026-08-27", "Qatar's Prime Minister visited Tehran on August 27 to discuss de-escalation.", False),
    ("brave",  "Iran ceasefire", "2026-07-08", "Donald Trump indicated on July 8 that a memorandum of understanding with Iran was over after Iranian attacks on commercial vessels in the Strait of Hormuz.", True),

    # ── Fed rate decision ─────────────────────────────────────────────────────
    ("linkup", "Fed rate", "2026-08-24", "The Federal Reserve held its benchmark interest rate steady at 3.5%–3.75% on August 24, 2026.", False),
    ("linkup", "Fed rate", "2026-08-24", "The Federal Reserve voted 9 to 3 to hold its benchmark interest rate steady on August 24, 2026.", False),
    ("linkup", "Fed rate", "2026-08-24", "Beth M Hammack, Neel Kashkari, and Lorie K Logan dissented from the Federal Reserve interest rate decision on August 24, 2026.", False),
    ("linkup", "Fed rate", "2026-08-24", "Jerome Powell is facing a Department of Justice criminal investigation regarding statements made to Congress about headquarters renovation costs.", True),

    ("brave",  "Fed rate", "2026-07-31", "The Federal Open Market Committee held the federal funds rate steady at 3.50%–3.75% for a fifth consecutive meeting in July 2026.", True),
    ("brave",  "Fed rate", "2026-09-16", "The Federal Reserve is scheduled to announce its next interest rate decision on Wednesday, September 16, 2026.", False),
    ("brave",  "Fed rate", "2026-10-07", "Minutes from the September 15–16 FOMC meeting are scheduled for release on October 7, 2026 at 2:00 PM Eastern Time.", False),
    ("brave",  "Fed rate", "2026-08-19", "FOMC minutes from the previous meeting were released on August 19, 2026.", True),

    # ── EU AI Act ─────────────────────────────────────────────────────────────
    ("linkup", "EU AI Act", "2026-08-02", "EU AI Act enforcement began on August 2, 2026, marking the full enforcement of high-risk AI system obligations under Annex III and transparency requirements of Article 50.", False),
    ("linkup", "EU AI Act", "2026-08-02", "The European Commission's enforcement powers over general-purpose AI model providers became active on August 2, 2026.", False),
    ("linkup", "EU AI Act", "2025-02-01", "Article 5 prohibitions against unacceptable AI practices went into effect in February 2025.", True),
    ("linkup", "EU AI Act", "2025-08-01", "General-purpose AI obligations started in August 2025.", True),
    ("linkup", "EU AI Act", "2026-08-02", "High-risk rules under the EU AI Act were partially deferred to December 2, 2027, under the Digital Omnibus package.", False),

    ("brave",  "EU AI Act", "2026-08-02", "The enforcement powers of the AI Office and national competent authorities of Member States became applicable on August 2, 2026.", False),
    ("brave",  "EU AI Act", "2026-08-02", "Article 50 general transparency requirements apply to any AI system placed on the EU market starting August 2, 2026.", False),
    ("brave",  "EU AI Act", "2026-12-02", "The prohibitions related to the generation or manipulation of non-consensual intimate material and child sexual abuse material apply from December 2, 2026.", False),
    ("brave",  "EU AI Act", "2027-12-02", "The rules for high-risk AI systems listed in Annex III to the AI Act apply from December 2, 2027.", True),
    ("brave",  "EU AI Act", "2028-08-02", "The rules for high-risk AI systems embedded into regulated products apply from August 2, 2028.", True),
    ("brave",  "EU AI Act", "2026-07-27", "EU Regulation 2026/1744, known as the Digital Omnibus on AI, entered into force on July 27, 2026.", True),
    ("brave",  "EU AI Act", "2026-08-14", "EU enforcers asked more than 30 AI companies to detail how they comply with European copyright rules.", False),

    # ── Bitcoin ───────────────────────────────────────────────────────────────
    ("linkup", "Bitcoin", "2026-08-11", "On August 11, 2026, Bitcoin was trading around $32,400.", False),
    ("linkup", "Bitcoin", "2026-08-21", "On August 21, 2026, Bitcoin surged to approximately $76,590.", False),
    ("linkup", "Bitcoin", "2026-08-24", "On August 24, 2026, Bitcoin prices reached near $78,976.", False),
    ("linkup", "Bitcoin", "2026-08-26", "On August 26, 2026, Bitcoin opened at $78,528 and rose to $78,585.", False),

    ("brave",  "Bitcoin", "2026-08-21", "The market price for a single Bitcoin was $76,712.47 at 8 a.m. Eastern Time on August 21, 2026.", False),
    ("brave",  "Bitcoin", "2009-01-01", "Developer Laszlo Hanyecz famously spent 10,000 Bitcoins on pizza in the past.", True),
    ("brave",  "Bitcoin", "2026-08-26", "At 7:15 a.m. Eastern Time on August 26, 2026, one Bitcoin was priced at $78,745.95.", False),
    ("brave",  "Bitcoin", "2026-08-24", "At 9 a.m. Eastern Time on August 24, 2026, the price of one Bitcoin was $78,976.18.", False),
    ("brave",  "Bitcoin", "2026-08-26", "Bitcoin traded around $78,700 on August 26, 2026, following a rally above $80,000.", False),
    ("brave",  "Bitcoin", "2026-08-27", "The Jackson Hole Symposium is scheduled for August 27-29, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-27", "The Bitcoin Asia 2026 conference was scheduled for August 27-28 in Hong Kong.", False),
    ("brave",  "Bitcoin", "2026-08-25", "Bitcoin opened at $78,982.27 on Tuesday, August 25, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-25", "Ethereum opened at $2,482.37 on Tuesday, August 25, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-26", "Bitcoin was trading near $78,493 on August 26, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-24", "Ethereum opened at $2,463.09 on Monday, August 24, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-24", "Bitcoin opened at $77,727.62 on Monday, August 24, 2026.", False),
    ("brave",  "Bitcoin", "2026-08-25", "At 8 a.m. Eastern Time on August 25, 2026, the price of Bitcoin was $79,111.64.", False),

    # ── Gaza ceasefire ────────────────────────────────────────────────────────
    ("linkup", "Gaza", "2025-01-15", "Israeli and Hamas negotiators agreed to a six-week ceasefire deal featuring three phases in January 2025.", True),
    ("linkup", "Gaza", "2025-12-31", "Israel violated the ceasefire nearly 600 times between October 2025 and December 2025.", True),
    ("linkup", "Gaza", "2025-12-31", "Israeli military operations killed at least 356 Palestinians and injured over 900 people between October 2025 and December 2025.", True),
    ("linkup", "Gaza", "2026-06-06", "A new Hamas delegation arrived in Cairo for talks on advancing the ceasefire and discussing a transition to its next phase in June 2026.", False),

    ("brave",  "Gaza", "2026-08-26", "Nikolay Mladenov criticized Israel for its military attacks on the Palestinian territory.", False),
    ("brave",  "Gaza", "2026-08-26", "Nikolay Mladenov stated to the U.N. Security Council that Trump's 20-point plan has moved from the negotiating table to the engineering table.", False),
    ("brave",  "Gaza", "2024-05-31", "The United States announced a ceasefire framework on 31 May 2024.", True),
    ("brave",  "Gaza", "2024-02-10", "Hamas suspended the release of Israeli hostages on 10 February.", True),
    ("brave",  "Gaza", "2024-02-15", "Hamas resumed the release of hostages on 15 February.", True),
    ("brave",  "Gaza", "2026-07-30", "Donald Trump announced that the Board of Peace agreed to a deal with Hamas involving armed groups putting down their weapons.", True),
    ("brave",  "Gaza", "2026-08-26", "Nickolay Mladenov and Benjamin Netanyahu agreed on a mechanism to resolve remaining questions during a meeting.", False),
    ("brave",  "Gaza", "2026-08-26", "At least 1,303 Palestinians, including 300 children, were killed in Israeli attacks in Gaza since the US-brokered ceasefire began.", True),
    ("brave",  "Gaza", "2026-08-28", "Israel has removed two Dutch diplomats from the ceasefire center.", False),
    ("brave",  "Gaza", "2026-08-28", "Israeli airstrikes in Gaza killed five people.", False),
    ("brave",  "Gaza", "2026-08-26", "Noa Furman stated that Israel continues to support Donald Trump's broader plan and cooperates to secure Hamas' disarmament.", False),
]

TOPICS = ["Iran ceasefire", "Fed rate", "EU AI Act", "Bitcoin", "Gaza"]


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str], provider: str = "gemini") -> list[list[float]]:
    """Embed all texts in one batched call using the specified provider."""
    from truebrief.llm.client import LLMClient
    from config.settings import settings
    # Force the provider for this run — don't rely on .env
    original = settings.EMBED_PROVIDER
    settings.EMBED_PROVIDER = provider
    try:
        llm = LLMClient()
        return llm.embed_batch(texts)
    finally:
        settings.EMBED_PROVIDER = original


def cosine(a, b) -> float:
    av, bv = np.array(a, dtype=float), np.array(b, dtype=float)
    d = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / d) if d > 0 else 0.0


# ── Temporal adjustment (mirrors arbiter/temporal.py) ─────────────────────────

def date_gap_days(d1: str, d2: str) -> int:
    try:
        a = datetime.date.fromisoformat(d1[:10])
        b = datetime.date.fromisoformat(d2[:10])
        return abs((a - b).days)
    except Exception:
        return 0


def temporal_penalty(gap_days: int) -> float:
    """Mirrors arbiter.temporal_overlap: large gap reduces similarity score."""
    if gap_days == 0:
        return 0.0
    if gap_days <= 1:
        return 0.03
    if gap_days <= 7:
        return 0.08
    if gap_days <= 30:
        return 0.15
    return 0.25


# ── Dedup simulation ───────────────────────────────────────────────────────────

@dataclass
class SimAlpha:
    idx: int
    provider: str
    topic: str
    date: str
    text: str
    is_background: bool
    embedding: list = field(default_factory=list)


@dataclass
class DedupResult:
    alpha: SimAlpha
    decision: str   # NEW / DUPLICATE / GREY_ZONE
    merged_into: Optional[int] = None  # idx of the alpha this was merged into
    raw_cosine: float = 0.0
    adj_cosine: float = 0.0


def simulate_dedup(alphas: list[SimAlpha]) -> list[DedupResult]:
    """
    Simulate the production arbiter fast-path for a list of alphas (in order).
    Each incoming alpha is compared against all already-accepted alphas.
    No LLM judge — GREY_ZONE is flagged but not resolved (conservative: treat as NEW).
    """
    accepted: list[SimAlpha] = []
    results: list[DedupResult] = []

    for a in alphas:
        if not accepted:
            accepted.append(a)
            results.append(DedupResult(a, "NEW"))
            continue

        best_adj = 0.0
        best_raw = 0.0
        best_idx = -1

        for prev in accepted:
            raw = cosine(a.embedding, prev.embedding)
            gap = date_gap_days(a.date, prev.date)
            adj = max(0.0, raw - temporal_penalty(gap))
            if adj > best_adj:
                best_adj = adj
                best_raw = raw
                best_idx = prev.idx

        if best_adj >= AUTO_MERGE_THRESHOLD:
            results.append(DedupResult(a, "DUPLICATE", merged_into=best_idx,
                                       raw_cosine=best_raw, adj_cosine=best_adj))
        elif best_adj >= GREY_ZONE_MIN:
            # In production this goes to LLM judge; here we treat as NEW (conservative)
            results.append(DedupResult(a, "GREY_ZONE", merged_into=best_idx,
                                       raw_cosine=best_raw, adj_cosine=best_adj))
            accepted.append(a)
        else:
            results.append(DedupResult(a, "NEW", raw_cosine=best_raw, adj_cosine=best_adj))
            accepted.append(a)

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def run_with_embedder(alphas: list[SimAlpha], embed_provider: str) -> dict:
    """Embed all alphas with given provider, run dedup per topic/provider, return summary."""
    texts = [a.text for a in alphas]
    print(f"  Embedding {len(texts)} alphas with {embed_provider}...", end=" ", flush=True)
    embeddings = embed_texts(texts, provider=embed_provider)
    for a, emb in zip(alphas, embeddings):
        a.embedding = emb
    print("done.")

    grand = {"linkup": {"NEW": 0, "GREY_ZONE": 0, "DUPLICATE": 0},
             "brave":  {"NEW": 0, "GREY_ZONE": 0, "DUPLICATE": 0}}
    topic_details = {}

    for topic in TOPICS:
        topic_alphas = [a for a in alphas if a.topic == topic]
        topic_details[topic] = {}
        for provider in ("linkup", "brave"):
            pa = [a for a in topic_alphas if a.provider == provider]
            results = simulate_dedup(pa)
            counts = {"NEW": 0, "GREY_ZONE": 0, "DUPLICATE": 0}
            for r in results:
                counts[r.decision] += 1
                grand[provider][r.decision] += 1
            topic_details[topic][provider] = (counts, results, pa)

    return {"grand": grand, "topics": topic_details}


def print_comparison(local_data: dict, gemini_data: dict) -> None:
    print(f"\n{'='*70}")
    print(f"  EMBEDDING COMPARISON: Local (BGE) vs Gemini-embedding-2")
    print(f"  AUTO_MERGE >= {AUTO_MERGE_THRESHOLD} | GREY_ZONE [{GREY_ZONE_MIN}, {AUTO_MERGE_THRESHOLD})")
    print(f"{'='*70}")

    for topic in TOPICS:
        print(f"\n  [{topic}]")
        print(f"  {'Provider':<10} {'In':>4}  {'Local: N/G/D':>14}  {'Gemini: N/G/D':>14}")
        for prov in ("linkup", "brave"):
            lc, _, _ = local_data["topics"][topic][prov]
            gc, _, _ = gemini_data["topics"][topic][prov]
            n = lc["NEW"] + lc["GREY_ZONE"] + lc["DUPLICATE"]
            l_str = f"{lc['NEW']}/{lc['GREY_ZONE']}/{lc['DUPLICATE']}"
            g_str = f"{gc['NEW']}/{gc['GREY_ZONE']}/{gc['DUPLICATE']}"
            print(f"  {prov:<10} {n:>4}  {l_str:>14}  {g_str:>14}")

    print(f"\n{'='*70}")
    print(f"  GRAND TOTALS")
    print(f"{'='*70}")
    print(f"  {'':20} {'LOCAL':>10}  {'GEMINI':>10}")
    for prov in ("linkup", "brave"):
        lg = local_data["grand"][prov]
        gg = gemini_data["grand"][prov]
        lt = sum(lg.values()); gt = sum(gg.values())
        l_dup_r = lg["DUPLICATE"] / lt * 100 if lt else 0
        g_dup_r = gg["DUPLICATE"] / gt * 100 if gt else 0
        l_grey_r = lg["GREY_ZONE"] / lt * 100 if lt else 0
        g_grey_r = gg["GREY_ZONE"] / gt * 100 if gt else 0
        print(f"\n  [{prov.upper()}]")
        print(f"  {'Auto-collapse %':20} {l_dup_r:>9.0f}%  {g_dup_r:>9.0f}%")
        print(f"  {'Grey zone %':20} {l_grey_r:>9.0f}%  {g_grey_r:>9.0f}%")
        print(f"  {'Survive (N+Grey)':20} {lg['NEW']+lg['GREY_ZONE']:>10}  {gg['NEW']+gg['GREY_ZONE']:>10}")

    # Show any pairs that differ between embedders (DUP in one, not the other)
    print(f"\n  KEY DIFFERENCES (pairs scored differently by each embedder):")
    found_diff = False
    for topic in TOPICS:
        for prov in ("linkup", "brave"):
            _, l_results, pa = local_data["topics"][topic][prov]
            _, g_results, _  = gemini_data["topics"][topic][prov]
            for lr, gr in zip(l_results, g_results):
                if lr.decision != gr.decision:
                    found_diff = True
                    print(f"  [{topic}][{prov}] LOCAL={lr.decision}(sim={lr.adj_cosine:.3f}) GEMINI={gr.decision}(sim={gr.adj_cosine:.3f})")
                    print(f"    {lr.alpha.text[:90]}")
    if not found_diff:
        print(f"  None — both embedders agree on every decision.")


def main():
    print(f"\nDedup quality test — {TODAY}")
    print(f"Comparing LOCAL (BGE bge-base-en-v1.5) vs GEMINI (gemini-embedding-2)")
    print(f"AUTO_MERGE >= {AUTO_MERGE_THRESHOLD} | GREY_ZONE [{GREY_ZONE_MIN}, {AUTO_MERGE_THRESHOLD})\n")

    alphas_local  = [SimAlpha(i, p, t, d, txt, bg) for i, (p, t, d, txt, bg) in enumerate(RAW_ALPHAS)]
    alphas_gemini = [SimAlpha(i, p, t, d, txt, bg) for i, (p, t, d, txt, bg) in enumerate(RAW_ALPHAS)]

    local_data  = run_with_embedder(alphas_local,  "local")
    gemini_data = run_with_embedder(alphas_gemini, "gemini")
    print_comparison(local_data, gemini_data)


if __name__ == "__main__":
    main()
