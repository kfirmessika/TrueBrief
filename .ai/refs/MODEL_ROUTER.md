# Model Router — Quick Reference
> Condensed from the full router. For detailed examples, see `docs/MODEL_ROUTER.md`.

## Decision Tree (follow in order, stop at first YES)

| Question | Model |
|---|---|
| Needs whole codebase or >50 files? | GEM-LOW → GEM-HIGH → GEM-PRO-C |
| Spec is vague / needs design judgment? | OPUS-AG → OPUS-C |
| Deep reasoning, algorithm, math? | GEM-HIGH |
| Multi-file feature, review, integration tests? (clear spec) | SON-AG → SON-C |
| Image/screenshot to UI? | GEM-LOW → GEM-PRO-C |
| Everything else? | **FLASH** (free, unlimited) |

## Task Cheatsheet

| Task | Model |
|---|---|
| Boilerplate, scaffold, simple edits | FLASH |
| Unit tests, docs, DevOps, formatting | FLASH |
| Map updates, file cleanup, refactoring (clear instructions) | FLASH |
| Multi-file feature (clear spec) | SON-AG |
| Code review, integration tests | SON-AG |
| Architecture, system design, ambiguous decisions | OPUS-AG |
| Algorithm design, hard debugging | GEM-HIGH |
| Big context (>50 files) | GEM-LOW |

## Hard Rules
- **FLASH first.** It's free. Use it for everything possible.
- **Never use OPUS for FLASH-tier tasks.** Even free Opus credits are too valuable.
- **GEM-LOW before GEM-HIGH.** HIGH costs ~26x more.

---

## ⚡ Complexity-Based Execution Patterns (NEW)
> **The 4-phase (PLAN/BUILD/UNIT/INTG) loop is COLLAPSED by complexity.** Do not blindly run 4 separate runs for every task.
> **Lesson learned:** Flash left circular imports, missing deps, and untestable lazy imports in RUN 08. Sonnet paid a "rework tax" fixing them in RUN 09. Prevent this by matching task complexity to execution pattern.

| Complexity Score | Pattern | Runs | Who Does What |
|:---:|:---|:---:|:---|
| ≤5 (trivial) | **ATOMIC** | 1 | FLASH: PLAN + BUILD + UNIT + INTG in one shot |
| 6–10 (medium / UI) | **SPEC+SHIP** | 2 | SONNET: PLAN+SPEC → FLASH: BUILD+UNIT+INTG |
| 11–18 (complex / logic) | **GUIDED BUILD** | 3 | SONNET: PLAN+SPEC → FLASH: BUILD+UNIT → SONNET: INTG+verify |
| ≥19 (architectural) | **FULL CYCLE** | 4 | OPUS: PLAN → SONNET: SPEC+validate → FLASH: BUILD+UNIT → SONNET: INTG |

### Pattern Rules
- **ATOMIC:** Flash reads the STEP_SPEC it writes itself, builds + tests, updates status. Zero Sonnet spend.
- **SPEC+SHIP:** Sonnet produces a *zero-ambiguity* spec (all types, imports, test targets explicit). Flash executes mechanically. If Flash drifts from spec, it's a spec failure, not a Flash failure.
- **GUIDED BUILD:** Sonnet owns INTG because complex logic needs senior verification (real backend, auth flows, 402/429 paths). Flash only owns the mechanical build.
- **FULL CYCLE:** Reserved for cross-cutting architecture (Stripe, Auth, Plugin system). OPUS sets the contract; Sonnet validates before handoff to Flash.

### Anti-Patterns to Avoid
- ❌ **Flash planning complex logic** (C≥11) — Flash will hallucinate import paths, create circular deps
- ❌ **Sonnet doing trivial UNIT-only runs** — Waste. Flash handles all unit tests.
- ❌ **Splitting C≤5 tasks into 4 runs** — Each run re-reads BOOT+state = ~2K tokens overhead per split
- ❌ **Calling INTG "done" based only on MSW mocks** — Real backend smoke test is always required for C≥10
