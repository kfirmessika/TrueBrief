# STEP 3.17 — Mobile-Responsive Design

**Complexity:** 8 | **Model:** FLASH  
**Phase:** 3 — Frontend + Monetization

---

## Goal

Ensure every page and component in the TrueBrief frontend renders correctly on mobile viewports (320px–768px). Fix all identified mobile-responsiveness gaps so the app is fully usable on phones and small tablets with no layout breaks.

---

## Issues to Fix

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `Navbar.tsx` | Links hidden on mobile with no fallback | Add hamburger menu + slide-down drawer |
| 2 | `page.tsx` (landing) | Hero `text-5xl` too large on small phones | `text-3xl sm:text-4xl md:text-5xl lg:text-7xl` |
| 3 | `page.tsx` (landing) | `scale-105` on pricing card overflows on mobile | Remove scale on mobile: `sm:scale-105` |
| 4 | `DashboardClient.tsx` | Empty state `p-20` excessive on mobile | `p-6 sm:p-12 md:p-20` |
| 5 | `history/page.tsx` | Empty state `p-16` excessive on mobile | `p-6 sm:p-12 md:p-16` |
| 6 | `TopicCard.tsx` | Action buttons only visible on hover (unusable on mobile) | Always visible on mobile, hover-only on `md:` |
| 7 | `AddTopicForm.tsx` | `pr-32` input + absolute button overflows narrow screens | Flex row layout, remove absolute positioning |
| 8 | `UpgradeBanner.tsx` | Decorative blur `w-48 h-48` fixed size overflows | `w-32 h-32 sm:w-48 sm:h-48` |

---

## Files Touched

| File | Change |
|------|--------|
| `frontend/src/components/layout/Navbar.tsx` | Add mobile hamburger menu |
| `frontend/src/app/page.tsx` | Hero text, pricing card scale |
| `frontend/src/app/dashboard/DashboardClient.tsx` | Empty state padding |
| `frontend/src/app/history/page.tsx` | Empty state padding |
| `frontend/src/components/topics/TopicCard.tsx` | Mobile-visible action buttons |
| `frontend/src/components/topics/AddTopicForm.tsx` | Flex layout for input+button |
| `frontend/src/components/topics/UpgradeBanner.tsx` | Responsive blur size |

---

## Acceptance Criteria

- [ ] Navbar renders a hamburger button on mobile; tapping it shows/hides all nav links
- [ ] Landing page hero heading readable on 320px viewport
- [ ] Pricing card highlighted variant does not overflow its column on mobile
- [ ] Dashboard and history empty states have comfortable padding on mobile
- [ ] TopicCard action buttons visible without hover on mobile
- [ ] AddTopicForm input + submit button usable on narrow screens
- [ ] `npm run build` passes
- [ ] No regressions on desktop (md: and above identical to before)

---

## Commit

```
p3-s17: mobile-responsive design — navbar menu, layout fixes, touch UX
```
