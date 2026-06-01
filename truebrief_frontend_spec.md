# TrueBrief — Frontend UX/UI Specification
> Covers: App Shell, Sidebar, New Topic page, Topic View page.
> Replaces steps 3.8, 3.9, 3.10, 3.12 in phase_3.md.
> Build exactly this. No deviations without updating this doc first.

---

## 1. App Shell (Persistent Layout)

Two-panel layout. Fixed sidebar left, scrollable main content right. Persistent across ALL views.

```
┌──────────────────────────────────────────────────────────┐
│  Sidebar (240px fixed)  │  Main content (flex: 1)        │
│                         │                                 │
│                         │  [view-specific content]        │
│                         │                                 │
└──────────────────────────────────────────────────────────┘
```

- Sidebar: `width: 240px`, `min-width: 240px`, not collapsible in Phase 3
- Main: `flex: 1`, `overflow-y: auto`, `background: var(--color-background-primary)`
- Full height: `100vh`, `display: flex`
- Dividing border: `0.5px solid var(--color-border-tertiary)`

The main panel renders different content depending on active view:
- No topic selected → New Topic page
- Topic selected → Topic View page
- Dashboard nav item → Dashboard page (Phase 3)

This is a **single-page app pattern** — no full page navigations. Clicking items in the sidebar
swaps the main panel content. URL updates via `router.push()` but no page reload occurs.

---

## 2. Sidebar Specification

Identical structure across all views. Only the active/highlighted item changes.

### 2.1 Structure (top to bottom)

```
[TB logo]  TrueBrief
────────────────────────
[+] New topic
[🔍] Search briefs...
────────────────────────
[⊞] Dashboard             [5]
────────────────────────
MY TOPICS
● EU AI Regulation        [2]
○ TSMC Semiconductors
● Tesla & EVs             [1]
◌ Israel Tech Sector      scanning...
● Fed Policy              [2]
○ OpenAI & Anthropic
────────────────────────
⚙ Settings
[KM] Kfir Messika         Pro
```

### 2.2 Header

- Logo icon: 26×26px rounded square (`border-radius: 6px`), `background: #0F6E56`, white "TB" text at 11px/500
- App name "TrueBrief" at 14px/500, `color: var(--color-text-primary)`
- Padding: 14px 14px 10px

### 2.3 New topic button

- Full width minus 20px horizontal margin
- `padding: 7px 12px`, `border-radius: var(--border-radius-md)`
- Icon: `ti-plus` at 14px, left-aligned
- Label: "New topic"

**Default state** (any other view is active):
- `background: var(--color-background-primary)`
- `border: 0.5px solid var(--color-border-secondary)`
- `color: var(--color-text-secondary)`

**Active state** (New Topic view is showing):
- `background: #E1F5EE`
- `border: 0.5px solid #A3D9C5`
- `color: #085041`, `font-weight: 500`

### 2.4 Search field

- Below New topic button, full width minus 20px margin
- `padding: 6px 10px`, `border-radius: var(--border-radius-md)`
- `border: 0.5px solid var(--color-border-tertiary)`, `background: var(--color-background-primary)`
- Icon: `ti-search` at 12px, placeholder "Search briefs..."
- Font-size 12px, `color: var(--color-text-tertiary)`
- Phase 3: non-functional placeholder (renders but no interaction)

### 2.5 Dashboard nav item

- `padding: 8px 12px`, `margin: 2px 8px`, `border-radius: var(--border-radius-md)`
- Icon: `ti-layout-grid` at 14px, `color: var(--color-text-secondary)`
- Label: "Dashboard", 13px/500
- Unread badge (right): coral `background: #FAECE7`, text `#993C1D`, 10px/500, shows total unread across all topics, hidden when 0
- Hover: `background: var(--color-background-tertiary)`
- Active: `background: var(--color-background-primary)`

### 2.6 "MY TOPICS" section label

- 10px, uppercase, `letter-spacing: 0.06em`, `color: var(--color-text-tertiary)`, 500
- `padding: 10px 14px 3px`

### 2.7 Topic list items

Each topic: `padding: 6px 12px`, `margin: 1px 8px`, `border-radius: var(--border-radius-md)`

```
[status dot]  [topic name]              [unread badge]
```

**Status dot** — 7×7px circle, `border-radius: 50%`:
- Red `#D85A30`: has unread updates
- Gray `var(--color-border-secondary)`: no new updates
- Amber `#EF9F27` + CSS pulse (`@keyframes`: 0%/100% opacity 1 → 50% opacity 0.3, 1.5s infinite): currently scanning

**Topic name**: 13px, truncated with ellipsis, `flex: 1`

**Unread badge**: same coral style as Dashboard badge. Hidden when 0.

**"scanning..." text**: replaces badge during scan. 10px, `color: var(--color-text-tertiary)`

**Hover**: `background: var(--color-background-tertiary)`
**Active** (this topic's view is showing): `background: var(--color-background-primary)`

### 2.8 Footer (pinned to bottom)

`margin-top: auto`, `border-top: 0.5px solid var(--color-border-tertiary)`, `padding: 6px`

- Settings row: `ti-settings` at 14px + "Settings" text, 12px
- User row: 26px avatar circle (`background: #0F6E56`, white initials, `border-radius: 50%`) + name + plan badge
- Plan badge: `background: var(--color-background-info)`, `color: var(--color-text-info)`, 10px, shows "Free" / "Pro" / "Power"
- Both rows: hover `background: var(--color-background-tertiary)`

---

## 3. New Topic Page

### 3.1 What it is

The screen for creating a new tracked topic. Replaces the old onboarding flow — first-time users
land here automatically. NOT a route — rendered by swapping main panel content.

Mental model: the "New Chat" screen from ChatGPT/Claude, adapted for news tracking.

### 3.2 Layout

Content is centered horizontally, positioned ~60px from the top (not fully vertically centered).
`display: flex`, `flex-direction: column`, `align-items: center`, `padding: 60px 24px 44px`

### 3.3 Headline

```
What's worth your attention?
```

- 22px, `font-weight: 500`, `color: var(--color-text-primary)`, `text-align: center`
- `margin-bottom: 24px`
- No subtitle beneath it

### 3.4 Input shell

Pill-shaped text area. The primary action element.

- `width: 100%`, `max-width: 420px`
- `border-radius: 22px` — noticeably pill-shaped
- `border: 0.5px solid var(--color-border-secondary)` at rest
- `border-color: #0F6E56` on focus
- `background: var(--color-background-primary)`
- `transition: border-color 0.2s`

**Textarea inside:**
- `padding: 14px 18px 10px`, `border: none`, `outline: none`, `resize: none`
- `font-size: 14px`, `color: var(--color-text-primary)`, `background: transparent`
- `min-height: 52px`, `max-height: 100px`, auto-expands on input
- `line-height: 1.6`
- Placeholder: `"Tell me what to watch... e.g. Apple, Fed rates, EU AI regulation"`
- NO microphone icon. NO attachment (+) icon. NO voice button.

Auto-resize JS:
```javascript
el.style.height = 'auto';
el.style.height = Math.min(el.scrollHeight, 100) + 'px';
```

### 3.5 Input bar (inside shell, below textarea)

`display: flex`, `align-items: center`, `justify-content: flex-end`, `gap: 5px`
`padding: 7px 10px`, `border-top: 0.5px solid var(--color-border-tertiary)`

Contains: **Frequency pill** + **Coverage pill** + **Submit button** — all right-aligned.

#### Frequency pill

Label: currently selected option (default "Auto"). Icon: `ti-clock` at 11px. Chevron: `ti-chevron-down` at 10px.

Rest: `border: 0.5px solid var(--color-border-secondary)`, transparent bg, muted text.
Open: `border-color: #0F6E56`, `background: #E1F5EE`, `color: #085041`.

Clicking opens Frequency dropdown panel (see 3.6).

#### Coverage pill

Label: currently selected option (default "Standard"). Icon: `ti-scan` at 11px.
Same visual states as frequency pill.

Clicking opens Coverage dropdown panel (see 3.7).

#### Submit button

- 30×30px circle, `background: var(--color-text-primary)`, `border: none`, `border-radius: 50%`
- Icon: `ti-arrow-up` at 13px, `color: var(--color-background-primary)`
- Hover: `background: #0F6E56`
- `aria-label: "Track this topic"`

**On click:**
- Free user → show inline upgrade nudge below shell (no modal)
- Pro/Power → `POST /api/v1/topics` → navigate to new topic's view on success

### 3.6 Frequency dropdown panel

In-flow panel (not a floating overlay). Appears between the shell and pills row when frequency pill is clicked.
Closes when option selected or pill clicked again. Opening frequency closes coverage if open.

- `width: 100%`, `max-width: 420px`, `margin-top: 6px`
- `border: 0.5px solid var(--color-border-secondary)`, `border-radius: var(--border-radius-lg)`
- `background: var(--color-background-primary)`, `overflow: hidden`

**Options:**

| Option | Right badge | ⓘ tooltip text |
|--------|-------------|----------------|
| Auto | Recommended | "TrueBrief learns which sources update most for your topic and adjusts scan frequency automatically. No waste, no gaps." |
| Daily | Free | — |
| Hourly | Pro | "Scans every hour. Best for fast-moving topics like earnings, politics, or live events." |
| Custom interval | Pro | — |

Default selected: Auto.

**Each option row:**
- `padding: 10px 14px`, `border-bottom: 0.5px solid var(--color-border-tertiary)`, last item no border
- Hover + selected: `background: var(--color-background-secondary)`
- Option name: 13px/500, `color: var(--color-text-primary)`
- `ⓘ` icon (`ti-info-circle` at 13px) inline after name on options with tooltips
  - Clicking `ⓘ` toggles an inline info box below the option name (`e.stopPropagation()`)
  - Info box: 11px, `background: var(--color-background-tertiary)`, `border-radius: var(--border-radius-md)`, `padding: 5px 8px`

**Badges:**
- Recommended: `background: var(--color-background-secondary)`, `border: 0.5px solid var(--color-border-tertiary)`, `color: var(--color-text-tertiary)`
- Free: `background: var(--color-background-success)`, `color: var(--color-text-success)`
- Pro: `background: var(--color-background-info)`, `color: var(--color-text-info)`
- All: `font-size: 10px`, `padding: 2px 7px`, `border-radius: 10px`, `flex-shrink: 0`

Selecting an option updates the pill label and closes the panel.

### 3.7 Coverage dropdown panel

Same visual structure as Frequency. "Coverage" = how many sources are scanned per run.
More coverage = more sources = higher confidence nothing was missed.

**Options:**

| Option | Right badge | ⓘ tooltip text |
|--------|-------------|----------------|
| Quick | Free | — |
| Standard | Recommended | "Scans RSS feeds and Tavily. Strong coverage for most topics at low cost." |
| Thorough | Pro | "Adds Brave Search and Exa — scans a wider net including PDFs and less-indexed sources. Best for high-stakes topics." |

Default selected: Standard.

### 3.8 Suggestion pills row

Below the input shell (and below any open dropdown panel).
`width: 100%`, `max-width: 420px`, `margin-top: 14px`
`display: flex`, `flex-wrap: wrap`, `gap: 7px`, `justify-content: center`

**Default state (fewer than 2 characters typed):**

5 category shortcut pills:

| Label | Fills input with |
|-------|-----------------|
| Tech & AI | "AI regulation" |
| Finance | "Fed rates" |
| Geopolitics | "China Taiwan" |
| Science | "GLP-1 drugs" |
| Startups | "startup funding" |

Clicking fills the textarea and triggers the shared topic search. Does not submit.

**Suggestion state (2+ characters typed):**

`GET /api/v1/shared-topics?q={query}` — debounced 300ms.
Matching shared topics replace the default pills (max 5 results).
If no matches, show default pills (no error state).
Matching: case-insensitive substring on topic name.
Matched portion of name: wrapped in `<b>` tags (`font-weight: 500`, `color: #085041`).

**All pills — same style (no visual distinction between defaults and suggestions):**

- `padding: 5px 11px`, `border-radius: 20px`
- `border: 0.5px solid #A3D9C5`, `background: #F0FAF6`
- Hover: `background: #D7F3E9`, `border-color: #5DCAA5`
- Topic/category name: 12px, `color: var(--color-text-primary)`
- "Free" badge: 10px, `background: #0F6E56`, `color: white`, `padding: 1px 5px`, `border-radius: 8px`

**Subscribed state (pill clicked):**

1. `POST /api/v1/shared-topics/{id}/subscribe`
2. Pill transforms in-place:
   - Green check icon `ti-check` at 11px, `color: #0F6E56`
   - Topic name (not bolded)
   - "Following" badge: `background: #5DCAA5`, `color: white`
   - `cursor: default`
3. After 800ms: navigate to that topic's view

### 3.9 Tier enforcement

| Tier | Submit button | Frequency options | Coverage options |
|------|--------------|-------------------|-----------------|
| Free | Shows inline upgrade nudge, no modal | Auto + Daily only | Quick only |
| Pro | Creates private topic | All options | All options |
| Power | Creates private topic | All + 15min | All options |

**Upgrade nudge** (Free user hits submit):
- Inline below shell, no modal
- 12px, `color: var(--color-text-secondary)`, `text-align: center`
- Text: "Private topics need Pro. Follow a shared topic above (free), or upgrade."
- "Upgrade" → Stripe Checkout in new tab

### 3.10 Sidebar active state on New Topic view

- "New topic" button: `background: #E1F5EE`, `border: 0.5px solid #A3D9C5`, `color: #085041`, `font-weight: 500`
- No topic in list is highlighted
- Dashboard: not highlighted
- When user subscribes or submits: new topic added to sidebar list immediately (optimistic), amber scanning dot

### 3.11 API calls

```
GET /api/v1/shared-topics?q={query}         # debounced 300ms, min 2 chars
POST /api/v1/shared-topics/{id}/subscribe   # subscribe to shared topic
POST /api/v1/topics                         # create private topic (Pro)
  body: { query, frequency, coverage }
```

### 3.12 Component files

```
frontend/components/layout/AppShell.tsx
frontend/components/layout/Sidebar.tsx
frontend/components/pages/NewTopicPage.tsx
frontend/components/newTopic/TopicInput.tsx
frontend/components/newTopic/FrequencySelector.tsx
frontend/components/newTopic/CoverageSelector.tsx
frontend/components/newTopic/SuggestionPills.tsx
frontend/components/newTopic/SuggestionPill.tsx
frontend/hooks/useSharedTopicSearch.ts
```

`NewTopicPage` is NOT a Next.js route page. It is a component rendered by `AppShell`
when `activeView === 'new-topic'`.

---

## 4. Topic View Page

### 4.1 What it is

The view for a specific tracked topic. Shows all briefs as a continuous scrollable thread,
oldest at top, newest at bottom — exactly like a chat conversation in ChatGPT or iMessage.

Renders in the main panel when a topic is selected in the sidebar.

### 4.2 Layout

```
┌─ Sidebar ─────────────┬─ Main content ──────────────────────────┐
│ (as spec'd above)     │  [Sticky topic header]                   │
│                       │  ─────────── May 27 ───────────          │
│ ● EU AI Regulation    │  No new information                      │
│   ← active            │                                          │
│                       │  ─────────── May 28 ───────────          │
│                       │  [fact] [source icons] [×]               │
│                       │  9:15 AM                                  │
│                       │                                          │
│                       │  ─── May 30 ── [Unread · 3 new] ──      │
│                       │  [fact] [source icons] [×]               │
│                       │  8:04 AM                                  │
└───────────────────────┴──────────────────────────────────────────┘
```

On open: auto-scroll to bottom (most recent brief). `scrollTop = element.scrollHeight`

### 4.3 Sticky topic header

`position: sticky`, `top: 0`, `z-index: 10`, `background: var(--color-background-primary)`
`padding: 16px 22px 12px`, `border-bottom: 0.5px solid var(--color-border-tertiary)`

**Topic name:** 17px/500, `color: var(--color-text-primary)`, `margin-bottom: 3px`

**Meta row** (below name): 11px, `color: var(--color-text-tertiary)`, flex row, gap 7px
- `ti-clock` icon at 11px
- "Last scanned 2h ago · Next in 4h"
- Frequency badge: 10px, `border: 0.5px solid var(--color-border-secondary)`, `color: var(--color-text-secondary)`, `padding: 1px 6px`, `border-radius: 10px`

**No buttons in the header.** No share. No settings. No scan now.

### 4.4 Thread content area

`padding: 0 22px 32px`. Scrollable (within the `overflow-y: auto` main panel).

### 4.5 Date separators

Appear between groups of facts from different days.

```html
<div style="display:flex; align-items:center; gap:10px; margin:18px 0 10px;">
  <div style="flex:1; height:0.5px; background:var(--color-border-tertiary)"></div>
  <span style="font-size:11px; color:var(--color-text-tertiary); white-space:nowrap">May 28</span>
  <div style="flex:1; height:0.5px; background:var(--color-border-tertiary)"></div>
</div>
```

Format: "May 27", "May 28", "May 29", "May 30" — date only, no year unless previous year.

**Unread date separator** — for the first unread group, add an Unread badge inline:

```html
<span style="font-size:10px; padding:1px 7px; border-radius:10px;
  background:#FAECE7; color:#993C1D; font-weight:500; white-space:nowrap">
  Unread · 3 new
</span>
```

### 4.6 "No new information" state

For dates where the pipeline ran but found nothing new:

```
No new information
```

12px, `color: var(--color-text-tertiary)`, `font-style: italic`, `padding: 4px 0 8px`

### 4.7 Fact items (brief messages)

Each atomic fact from the pipeline is one "message" in the thread.

`padding: 10px 0`, `border-bottom: 0.5px solid var(--color-border-tertiary)`
Last item in thread: `border-bottom: none`

**Structure:**

```
[Fact text — full sentence]

[Source icon 1] [Source icon 2] [Source icon 3]          [×]
8:04 AM
```

**Fact text:** 13px, `color: var(--color-text-primary)`, `line-height: 1.6`, `margin-bottom: 7px`

**Source icons row:**
- `display: flex`, `align-items: center`, `margin-bottom: 4px`
- `sicons` flex: `gap: 4px`, `flex: 1`
- Each icon + delete button on same row, delete right-aligned

**Source icon circles:**
- 20×20px, `border-radius: 50%`
- Background = source brand color (see 4.8)
- White initials/abbreviation: 1 letter at 8px, 2 letters at 7px, 3 letters at 6px
- `cursor: pointer`
- Hover: `opacity: 0.7`
- Active (panel open): `outline: 2px solid var(--color-border-primary)`, `outline-offset: 2px`
- Clicking toggles source expansion panel (see 4.9)

**Delete button (×):**
- `ti-x` icon at 14px
- `background: none`, `border: none`, `cursor: pointer`
- `color: var(--color-text-tertiary)`, hover `color: var(--color-text-primary)`
- On click: fade item to `opacity: 0` (0.2s transition), then `display: none` after 220ms

**Timestamp:**
- Below the source icons row
- `font-size: 11px`, `color: var(--color-text-tertiary)`
- Format: "8:04 AM" (time only — the date is already in the separator above)
- Facts from the same pipeline run share the same timestamp

### 4.8 Source brand colors

Use these circle background colors per source. Add more as needed:

| Source | Abbreviation | Color |
|--------|-------------|-------|
| Reuters | R | `#1961A5` |
| Politico | P | `#1C3E6E` |
| Euractiv | E | `#0A7B6A` |
| Financial Times | FT | `#BE431B` |
| Ars Technica | AT | `#EA6B1F` |
| BBC | B | `#B4071A` |
| Bloomberg | BL | `#1A1A1A` |
| TechCrunch | TC | `#0A84FF` |
| CNBC | CN | `#005594` |
| NYT | NY | `#1A1A1A` |
| WSJ | WS | `#0274B6` |

In production: fetch actual favicon via `https://www.google.com/s2/favicons?domain={domain}&sz=32`
and render as a 20px circle image. Fall back to initial circle if favicon load fails.

### 4.9 Source expansion panel

Appears below the source icons row when a source icon is clicked.
Only one panel can be open at a time. Clicking same icon again closes it.
Clicking a different icon closes the current one and opens the new one.

- `margin-top: 7px`, `padding: 9px 12px`
- `border: 0.5px solid var(--color-border-tertiary)`, `border-radius: var(--border-radius-md)`
- `background: var(--color-background-secondary)`

**Panel header row:**
- Source name: 12px/500, `color: var(--color-text-primary)`
- "Read original" link: 11px, `color: var(--color-text-info)`, `ti-arrow-up-right` icon at 11px
- Opens original article URL in new tab

**Original sentence:**
- 12px, `color: var(--color-text-secondary)`, `line-height: 1.5`, `font-style: italic`
- The exact sentence extracted from the source article that produced this alpha

### 4.10 API calls

```
GET /api/v1/topics/{id}/briefs          # all briefs for topic, sorted oldest-first
  response: [
    {
      id, delivered_at, facts: [
        {
          id, alpha_text, published_at,
          sources: [{ name, domain, url, original_sentence }]
        }
      ]
    }
  ]

DELETE /api/v1/facts/{id}/dismiss       # soft-delete (user dismissed this fact)
```

Facts are grouped by brief (`delivered_at` date) for the date separator.
Facts within a brief share the same timestamp (the brief's `delivered_at` time).

### 4.11 Component files

```
frontend/components/pages/TopicViewPage.tsx
frontend/components/topicView/TopicHeader.tsx
frontend/components/topicView/BriefThread.tsx
frontend/components/topicView/DateSeparator.tsx
frontend/components/topicView/FactItem.tsx
frontend/components/topicView/SourceIcon.tsx
frontend/components/topicView/SourcePanel.tsx
frontend/hooks/useTopicBriefs.ts
```

### 4.12 States to handle

| State | What to show |
|-------|-------------|
| Loading briefs | Skeleton fact items (3 placeholder rows) |
| No briefs yet (new topic, first scan pending) | Centered message: "Your first scan is running. Check back in a few minutes." with amber pulsing dot |
| All dates have "no new information" | Thread shows the no-info messages but no facts |
| Fact dismissed (×) | Fade out, hide, no undo in Phase 3 |
| Source panel open | Panel below the fact item, icon has outline ring |
| Topic scanning now | Sidebar dot is amber + pulsing. No loading state in main panel. |

### 4.13 Acceptance criteria

- [ ] Topic header is sticky — stays visible while scrolling thread
- [ ] No share, settings, or scan now buttons anywhere on this page
- [ ] Page auto-scrolls to bottom on open
- [ ] Date separators appear between each day's facts
- [ ] "No new information" shown for dates with no facts
- [ ] Unread date separator shows coral badge "Unread · N new"
- [ ] Each fact shows its timestamp below the source icons
- [ ] Facts from same scan share the same timestamp
- [ ] Source icon click opens panel with original sentence + link
- [ ] Only one source panel open at a time
- [ ] Clicking same icon again closes panel
- [ ] × dismisses fact with 0.2s fade, optimistically removes from UI, calls DELETE API
- [ ] Dismissed facts do not reappear on page refresh
- [ ] Favicons load from Google favicon API, fall back to initial circles
- [ ] Page works in dark mode (all colors use CSS variables except brand colors)
- [ ] Page is mobile-responsive at 375px (sidebar collapses)

---

## 5. Dashboard Page

### 5.1 What it is

The home screen. Shows a feed of cards — one per topic that has new updates since the user last visited.
Topics with no new updates do not appear. No "caught up" section, no placeholders for quiet topics.
Users can see which topics are quiet from the sidebar (no badge = nothing new).

Renders in the main panel when Dashboard is selected in the sidebar.

### 5.2 Sidebar active state

- Dashboard nav item: `background: var(--color-background-primary)` (highlighted)
- No topic in the list is highlighted
- Unread badge on Dashboard item shows total unread count across all topics

### 5.3 Page header

`padding: 20px 22px 16px`

```
Dashboard
```

- "Dashboard": 20px/500, `color: var(--color-text-primary)`, `margin: 0`
- Nothing else. No subtitle. No "mark all read". No "time saved" widget.

### 5.4 Update cards

One card per topic that has updates. Cards appear in order of most recently updated first.
`padding: 0 22px 28px`

**Card container:**
- `border: 0.5px solid var(--color-border-tertiary)`, `border-radius: var(--border-radius-lg)`
- `padding: 14px 16px`, `margin-bottom: 10px`
- `cursor: pointer` — clicking anywhere on card navigates to that topic's view
- Hover: `border-color: var(--color-border-secondary)`

**Card header row** (`display: flex`, `justify-content: space-between`, `margin-bottom: 8px`):
- Topic name: 13px/500, `color: var(--color-text-primary)`
- Right: "2h ago · Hourly" — 11px, `color: var(--color-text-tertiary)`
  - Time since last scan + frequency cadence label

**Badges row** (`display: flex`, `gap: 6px`, `margin-bottom: 10px`, `flex-wrap: wrap`):
- "N new story/stories" pill: `background: #E1F5EE`, `color: #085041`, 11px/500, `padding: 2px 8px`, `border-radius: 10px`
- "N update/updates" pill: `background: #E6F1FB`, `color: #185FA5`, same sizing
- Show only the badges that apply. A topic with only updates shows no green pill.

**Preview text:**
- 13px, `color: var(--color-text-primary)`, `line-height: 1.5`, `margin-bottom: 10px`
- One sentence — the most significant new fact from this brief
- Not truncated — show the full sentence even if long

**"Read brief" link:**
- 12px, `color: var(--color-text-info)`
- `ti-arrow-right` icon at 11px inline
- Navigates to topic view, scrolled to this brief

### 5.5 Empty state

If ALL topics have no new updates (rare — only after the user reads everything):

```
You're all caught up.
```

- Centered in the main panel, 14px, `color: var(--color-text-tertiary)`, `font-style: italic`
- No illustration, no action buttons

### 5.6 API calls

```
GET /api/v1/dashboard
  response: [
    {
      topic_id, topic_name, frequency, last_scanned_at,
      new_count, update_count,
      preview_text        # the top alpha_text from this brief
    }
  ]
  # sorted by last_scanned_at desc
  # only topics with new_count > 0 OR update_count > 0
```

### 5.7 Component files

```
frontend/components/pages/DashboardPage.tsx
frontend/components/dashboard/UpdateCard.tsx
```

### 5.8 Acceptance criteria

- [ ] Only topics with updates appear — no empty/quiet topics shown
- [ ] Cards ordered by most recently scanned first
- [ ] Topic name, time ago, frequency cadence all correct
- [ ] Green badge for new stories, blue for updates, only shown when > 0
- [ ] Preview text is one full sentence, not truncated
- [ ] Clicking card navigates to topic view
- [ ] "Read brief →" link works identically to clicking the card
- [ ] Empty state shows when no topics have updates
- [ ] Dashboard badge in sidebar shows correct total unread count
- [ ] Badge disappears when count reaches 0
- [ ] No "mark all read", no "time saved", no "caught up" sections

---

## 6. Design Tokens (all pages)

| Token | Value | Used for |
|-------|-------|----------|
| TrueBrief green | `#0F6E56` | Logo, focus border, submit hover, Free badge bg, active state |
| Green light | `#E1F5EE` | Pill bg, New Topic active button bg |
| Green border | `#A3D9C5` | Pill border, active button border |
| Green medium | `#5DCAA5` | Pill hover border, Following badge bg |
| Green dark text | `#085041` | Pill matched text, active button text |
| Coral badge bg | `#FAECE7` | Unread count badges, Unread separator |
| Coral badge text | `#993C1D` | Unread count badge text |
| Coral dot | `#D85A30` | Topic status dot (has unread) |
| Amber dot | `#EF9F27` | Topic status dot (scanning) |
| Pulse animation | keyframes | Amber scanning dot: 0%/100% opacity 1, 50% opacity 0.3, 1.5s infinite |

All other colors use CSS variables (`var(--color-text-primary)` etc.) for automatic dark mode.

---

## 7. What This Replaces in phase_3.md

| Old step | Replacement |
|----------|-------------|
| 3.8 Topic Management UI | Section 3 (New Topic) + Section 4 (Topic View) of this spec |
| 3.9 Brief Display Page | Section 4 of this spec |
| 3.10 Brief History Page | Eliminated — history is the scrollable thread in Section 4 |
| 3.11 Landing Page | Not covered here — separate marketing doc needed |
| 3.12 Onboarding Flow | Eliminated — New Topic page serves as onboarding for new users |
| 3.13 "Time Saved" Metric | Eliminated — removed from Dashboard design |
| Dashboard (was step 3.8) | Section 5 of this spec |
