# TrueBrief Backlog

## MOBILE (2026-07-12 — built; see docs/MOBILE_APP.md for every command)
1. **[USER] Install the PWA on your phone** — deploy (or cloudflared tunnel) → open URL
   on phone → Add to Home screen. Push already works (VAPID).
2. **[USER] Android APK when wanted** — install Android Studio → `cd frontend/android &&
   ./gradlew assembleDebug`. Project is committed + icon-stamped; zero code work left.
3. **[USER] Set the real prod frontend URL** in `frontend/capacitor.config.ts`
   (PROD_URL, currently placeholder app.truebrief.app) → `npm run cap:sync`.
4. Later (post-store decision): FCM/APNs push inside native shells; @capacitor/browser
   for Google OAuth in-app. Both documented in MOBILE_APP.md §4.

## URGENT (2026-07-11)

1. **[USER] Search APIs are DEAD**: Tavily "exceeds plan usage limit" + Brave "402
   Payment Required" (seen live during benchmark run). Scans are collecting degraded
   (RSS/google_news only). Tavily paid plan ($30/mo, 4k credits) is now a day-1 cost.
2. **Re-run the judge benchmark AFTER search quota is restored** —
   `python scripts/quality_benchmark.py "iran war"`. Last completed run (07-05) LOST
   17-36 pre-fixes; the post-fix number is the launch-gate number.
3. **[USER] Backend must be started with the venv**: a system-python uvicorn ran from
   07-09→07-11 (every LLM call in the API silently crashed → empty story connectors,
   dead summaries). Also: killing the reload parent leaves a child holding :8000 —
   check `netstat -ano | findstr :8000` after stopping. Use `scripts/start-local.ps1`.
   Agent-restarted correctly on 07-11 (running now, PID group 20756/25300/26800).

## FORMULA TUNING (deferred — do after first users give feedback)
- Calibrate `_select_m_facts()` and `_adaptive_window()` in `src/truebrief/api/routes.py`.
  Specifically: are the M(N) caps correct (does a 40-alpha summary with 24 facts feel right?),
  and does the sentence window match what users expect (2-5 for 2 alphas; 5-11 for 24)?
  Run the scratchpad e2e test at `.../scratchpad/e2e_summary_endpoint.py` as a sanity check.
  Requires real user data to tune confidently — don't change before you have feedback.

## PRODUCT LAUNCH (2026-07-10 sprint — see docs/PRODUCT_PLAN.md for the full map)

1. **[USER] Apply migration 026** (`scripts/migrations/026_api_keys.sql`) in Supabase SQL
   editor — api_keys + api_usage_daily tables + increment_api_usage RPC. The developer
   API 503s without it.
2. **[USER] Paddle activation** — create Pro ($19) / Power ($49) prices, set
   `PADDLE_PRICE_PRO`, `PADDLE_PRICE_POWER`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`
   on Railway, then test one checkout end-to-end. Upgrade buttons in Settings are now
   wired and will surface config errors until this is done.
3. **[USER] Eyeball /terms and /privacy** — content matches real behavior but you own them.
4. Test-ordering flake: `test_limiter_uses_memory_without_redis` fails in the full suite,
   passes alone and in pairs — some earlier test leaks env/limiter state. Pre-existing,
   not urgent.
5. Webhooks for the developer API (push facts to customer URLs) — after first API users.

## LEFT FOR TOMORROW (from 2026-07-07 coverage sprint — see git tag `pre-coverage-sprint`)

1. **[USER] Groq Dev tier** — console.groq.com/settings/billing (~$1-3/mo).
   Free tier's 100k tokens/day died twice during validation. #1 reliability spend.
2. **[USER] Deploy to Railway** — all fixes are local commits on `main`; prod runs old
   code until pushed/deployed. `V4_SIGNAL_SCORER` is now the settings default (True),
   so no Railway env change needed.
3. **Off-topic history sweep** — `python scripts/cleanup_facts.py --off-topic --days 7 --apply`
   ONLY when Groq 70b has tokens (never delete history on flash-lite fallback verdicts).
   Dry-run first without `--apply`.
4. **Re-run the judge after a clean day** —
   `python scripts/validate_pipeline.py --topic-name "iran war" --days 1 --compare-gemini`
   Success bar: MISSING list ≤ 1-2 items, noise list only pre-fix leftovers.
5. **Stale-fact decay (design work, deferred until live users)** — superseded procedural
   facts ("talks scheduled Wednesday") linger in the accumulated view. This is the STALE
   classification from project_classification_research memory.
6. **Topic scope UX** — the gate correctly excludes Lebanon/Gaza from "iran war"
   (they land in the isreal topic). If the user wants whole-regional-war coverage,
   rename the topic accordingly; consider explaining scope at topic creation.
7. **Business (from 2026-07-07 assessment):** reposition as change-monitoring with
   evidence for ONE niche; push channel (email/Slack digest) before more dashboard;
   "we read 300 articles, 6 mattered" as the marketing metric; 10 design partners.

## SECURITY — verify on Railway (2026-07-07 audit, commit febfdf4)
- **[USER] Confirm these env vars are SET on Railway prod** (fixes now fail CLOSED,
  so if unset, admin endpoints deny everyone — safe, but you'd lose your own access):
  `FOUNDER_EMAIL` (=kfirmessika@gmail.com), and `ADMIN_EMAILS` or `ADMIN_USER_IDS`.
  Also confirm `FRONTEND_URL` is your real domain (billing redirect + CORS depend on it).
- Manual eyeball of `.env.example` (permission-blocked from me) — confirm placeholders only.
- SSRF note: if Railway egress is NOT segmented from a cloud metadata endpoint, the
  extractor SSRF fix is doing real work — keep url_guard on.

## Done 2026-07-07 (context)
- Security audit: fixed IDOR (fact delete), fail-open admin gates, scraped-URL XSS,
  SSRF on fetcher, verbose error leaks, unbounded raw_query, billing open-redirect.
  12 security tests, 227 backend tests green, frontend build clean. Commit febfdf4.
- SignalScorer (70b + on_topic) proven live: trump 34→13, iran 30→11, isreal 16→5, us 44→12
- Breaking-news fan-out: judge-flagged missing Hormuz vessel attack captured at 10/10
  within the hour of the fix
- Domain strategies rebuilt (trump/iran had 0 domains), dated queries, MAX_K 32
- 25 dup rows + 19 garbage + 22 off-topic rows deleted from prod; migrations 024/025 applied
