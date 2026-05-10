# STEP SPEC — 3.6: Next.js Frontend Skeleton
> **Status:** [ ] READY FOR BUILD | [ ] IN PROGRESS | [ ] VERIFIED
> **Mode:** PLAN + BUILD (RUN 07)
> **Builder:** Gemini Flash (this session)
> **Planner:** Gemini Flash (this session)
> **Date:** 2026-05-08

---

## 🎯 Objective
Initialize the `frontend/` directory with a production-grade Next.js 14+ skeleton using the App Router, Tailwind CSS, and TypeScript. Establish the core page structure (Dashboard, Onboarding, Brief History) and shared layout.

---

## 📐 Design & Logic

### 1. Framework & Tools
- **Framework:** Next.js (App Router)
- **Styling:** Tailwind CSS (Vanilla, no component libraries yet)
- **Language:** TypeScript (Strict)
- **Data Fetching:** React Query (TanStack Query) + Axios
- **Icons:** Lucide React (standard for Next.js/Tailwind stacks)

### 2. Directory Structure
```
frontend/
├── src/
│   ├── app/                # App Router (Next.js 13/14+)
│   │   ├── layout.tsx      # Root layout (QueryClient, Auth, Navbar)
│   │   ├── page.tsx        # Landing Page (/)
│   │   ├── dashboard/
│   │   │   └── page.tsx    # Topic List (/dashboard)
│   │   ├── onboarding/
│   │   │   └── page.tsx    # New user flow (/onboarding)
│   │   └── topics/
│   │       └── [id]/
│   │           ├── page.tsx        # Topic Detail (/topics/[id])
│   │           └── briefs/
│   │               ├── page.tsx    # Brief History (/topics/[id]/briefs)
│   │               └── [briefId]/
│   │                   └── page.tsx # Full Brief View (/topics/[id]/briefs/[briefId])
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Navbar.tsx
│   │   │   └── Footer.tsx
│   │   ├── ui/             # Reusable UI components (TopicCard, etc.)
│   │   └── shared/
│   ├── lib/
│   │   ├── api.ts          # Axios instance + API wrappers
│   │   └── query-client.ts # React Query configuration
│   └── types/              # Shared TS interfaces (Topic, Brief, etc.)
```

### 3. API Integration
- Backend URL: `http://localhost:8000/api/v1` (Development)
- Endpoint Map:
  - `GET /tiers`
  - `POST /checkout`
  - `POST /portal`
  - `GET /status/{user_id}`

---

## 📂 File GPS

**Reads:**
- `docs/blueprints/phase_3.md`
- `config/settings.py`

**Touches:**
- `frontend/` (Directory creation)
- `docs/blueprints/phase_3.md` (Update Status)
- `docs/core/EXECUTION_PLAN.md` (Update Status)

---

## 🛠 Execution Steps

1. [ ] **Scaffold Next.js App.** Run `npx create-next-app@latest frontend ...` with non-interactive flags.
2. [ ] **Install Dependencies.** `npm install @tanstack/react-query axios lucide-react`.
3. [ ] **Configure Shared Layout.**
    - Implement `QueryClientProvider` in `layout.tsx`.
    - Create `Navbar.tsx` and `Footer.tsx`.
4. [ ] **Create Route Placeholders.**
    - `/` (Landing)
    - `/dashboard` (Topic List)
    - `/onboarding` (Setup)
    - `/topics/[id]` (Detail)
5. [ ] **Setup API Client.**
    - Create `src/lib/api.ts` with Axios base configuration.
6. [ ] **Verify Build.** Run `npm run build` to ensure zero TS/Lint errors.
7. [ ] **Update Status.** Update Phase 3 blueprint and Execution Plan.

---

## ✅ Testing & Verification

### Unit Tests
- [ ] `npm run lint` passes.
- [ ] `npm run build` passes.

### Integration Check (Smoke Test)
- [ ] `npm run dev` starts.
- [ ] Accessing `localhost:3000/` shows "TrueBrief Landing".
- [ ] Accessing `localhost:3000/dashboard` shows "Topic Dashboard".

---

## 📝 Planner Notes
- **Interactivity:** Use `--no-interactive` and explicit flags to avoid blocking the agent.
- **Port Conflict:** Backend runs on 8000, Frontend on 3000.
- **Tailwind:** Ensure `tailwind.config.ts` includes the correct `content` paths for `src/`.
