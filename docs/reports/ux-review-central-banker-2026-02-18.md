# UX Review: SimCash Platform — Central Banker Persona

**Date:** 2026-02-18
**Reviewer:** Central bank researcher (payment systems division, European ECB-style institution)
**Platform version:** Local dev build, `feature/interactive-web-sandbox` branch

---

## Executive Summary

SimCash is an impressively ambitious research tool that models RTGS liquidity coordination games with AI agents. The documentation is exceptionally thorough and would impress any payments researcher. However, **the platform is blocked at the login screen for local dev use** — the frontend requires Firebase authentication even when the backend has `SIMCASH_AUTH_DISABLED=true`, making the "auth-free local testing" promise broken. Beyond this blocker, the code review reveals a well-structured but incomplete platform: the scenario library and policy library are rich, the game view has sophisticated features (tick replay, policy evolution, bootstrap statistics), but several views are stubs, the information hierarchy needs work, and a researcher would need more auditability features to trust the results.

---

## Methodology

### What was tested
- **Login page**: Visual inspection and screenshot via browser automation
- **Backend API**: Direct HTTP calls to all major endpoints (`/api/games/scenarios`, `/api/scenarios/library`, `/api/policies/library`, `/api/presets`, `/api/games`)
- **Frontend source code**: Full review of all 15 view components (~5,400 lines), key shared components, auth flow, API layer, and types
- **Documentation content**: Read all 14 doc sections (embedded in DocsView.tsx — ~1,800 lines of inline content)
- **Game creation**: Successfully created a game via API to verify backend flow

### What could NOT be tested (due to auth blocker)
- Actual rendering of any authenticated view
- Visual layout, alignment, responsive behavior, dark mode rendering
- Interactive flows (launching games, watching simulations, clicking through tabs)
- WebSocket game streaming behavior
- Chart rendering (SVG balance charts, Recharts evolution charts)

---

## Findings

### 1. Authentication & Onboarding

#### F1.1 — Frontend auth blocks local development [CRITICAL]
**Description:** The task instructions state `SIMCASH_AUTH_DISABLED=true` should enable auth-free access. The backend respects this environment variable and returns data without authentication. However, the React frontend has a hard dependency on Firebase Auth (`AuthContext.tsx` → `onAuthStateChanged`) and shows a login page with no bypass mechanism. There is no `VITE_AUTH_DISABLED` env var, no dev mode toggle, and no conditional rendering path for local development.

**Impact:** Any evaluator, researcher, or demo audience following the setup instructions is immediately blocked. This is the #1 barrier to adoption.

**Severity:** 🔴 CRITICAL

#### F1.2 — Login page lacks value proposition [MAJOR]
**Description:** The login screen shows "💰 SimCash — Interactive Payment Simulator" with Google sign-in and magic link options. A central banker seeing this for the first time gets zero information about what the tool does, why they should care, or what they'll see after signing in. No feature highlights, no screenshots, no institutional context.

**Screenshot ref:** Login page screenshot captured (dark page with logo + sign-in buttons).

**Severity:** 🟡 MAJOR

#### F1.3 — "Access restricted to authorized users" is unwelcoming [MINOR]
**Description:** The small text at the bottom of the login page says "Access restricted to authorized users." For a research tool meant to attract central bank researchers, this is off-putting. It should say something like "Request access to explore AI-powered payment system simulations" with a link to contact information.

**Severity:** 🟢 MINOR

---

### 2. Navigation & Information Architecture

#### F2.1 — Tab bar is overwhelming with 13 tabs [MAJOR]
**Description:** The main navigation shows up to 13 tabs: Setup, Scenarios, Policies, Create, Game, Dashboard, Agents, Events, Config, Replay, Analysis, Docs, Saved. Many are conditionally hidden (require active simulation/game), but even the base set (Setup, Scenarios, Policies, Create, Docs, Saved) is 6 tabs. A researcher doesn't know where to start.

**Recommendation:** Group into 3-4 top-level sections: Explore (Scenarios + Policies), Build (Create + Saved), Run (Game + Dashboard), Learn (Docs). Show contextual sub-navigation within each.

**Severity:** 🟡 MAJOR

#### F2.2 — "Setup" tab is labeled "home" internally but shows as "Setup" [MINOR]
**Description:** The first tab is labeled "🏠 Setup" but internally uses id `'home'`. It's actually a landing page with navigation cards + game launcher — not a "setup" step. This confuses the mental model.

**Severity:** 🟢 MINOR

#### F2.3 — No breadcrumb or "where am I" indicator in library detail views [MINOR]
**Description:** When clicking into a scenario or policy detail, the only navigation is a "← Back to Library/Policies" text link. No breadcrumb trail, no context about which category you came from.

**Severity:** 🟢 MINOR

---

### 3. Home/Setup View

#### F3.1 — Three launch modes are confusing [MAJOR]
**Description:** The Setup page offers three modes: "🎮 Multi-Day Game", "📋 Presets", and "🛠 Custom Builder". A researcher doesn't understand the distinction. "Multi-Day Game" is the main flow. "Presets" launches a single-day simulation with a different UI (WebSocket tick-streaming). "Custom Builder" is another single-day launcher. The dual launch paths (game mode vs. simulation mode) with different views (GameView vs. DashboardView) is architecturally sound but confusing to users.

**Recommendation:** Default to Multi-Day Game mode. Rename "Presets" to "Quick Single-Day Run" and mark as "Advanced". Consider merging Custom Builder into the Create tab.

**Severity:** 🟡 MAJOR

#### F3.2 — "Mock Mode" terminology is unclear [MINOR]
**Description:** The game settings include "Enable AI Optimization" with a "Mock Mode" toggle. A researcher doesn't know what "mock" means here. The tooltip says "(no API costs)" — but what does that mean for the simulation? Does mock mode produce meaningful results or random noise?

**Recommendation:** Rename to "Simulated AI" vs "Real AI (OpenAI API)" with clearer explanation of what the simulated mode does.

**Severity:** 🟢 MINOR

#### F3.3 — Cost rate tooltips are well done ✓ [POSITIVE]
**Description:** The scenario cards in game mode show cost parameters with helpful tooltips explaining what each cost means. The format "💰 83 bps", "⏱ 0.2/¢/tick", "⚠️ $500" is compact and informative. Good work.

#### F3.4 — "How It Works" is dismissible and may not be seen [MINOR]
**Description:** The collapsible "How It Works" section uses localStorage to remember dismissal. First-time users who dismiss it won't see it again even in different browsers on the same machine. More importantly, it's positioned between navigation cards and the launch UI — easy to skip entirely.

**Severity:** 🟢 MINOR

---

### 4. Scenario Library

#### F4.1 — Library is rich and well-categorized ✓ [POSITIVE]
**Description:** The API returns a large set of scenarios across categories (Paper Experiments, Crisis & Stress, LSM Exploration, General, Testing) with difficulty ratings, tags, feature lists, and cost configurations. The card-based browsing with category filters and difficulty badges is research-grade.

#### F4.2 — Descriptions are sometimes too long and developer-focused [MINOR]
**Description:** Some scenario descriptions (e.g., "Advanced Policy Crisis Scenario") read like developer changelogs: "This scenario demonstrates the latest policy system enhancements (Phases 3.3-4.5)..." A researcher doesn't know what "Phase 3.3" means. Descriptions should be research-focused: what question does this scenario answer?

**Severity:** 🟢 MINOR

#### F4.3 — No search functionality [MINOR]
**Description:** With 15+ scenarios, there's no text search. Category filters help, but a researcher looking for "bilateral" or "stress" scenarios has to scan visually.

**Severity:** 🟢 MINOR

#### F4.4 — "LLM Strategy Depth" in launch config is unexplained [MAJOR]
**Description:** The scenario detail launch panel has "Simple / Standard / Full" strategy depth options. These map to `constraint_preset` in the API. A researcher has no idea what these mean or how they affect the AI's behavior. No tooltip, no link to docs.

**Severity:** 🟡 MAJOR

---

### 5. Policy Library

#### F5.1 — 30+ policies with good metadata ✓ [POSITIVE]
**Description:** The policy library shows complexity ratings, actions used, decision tree node counts, context fields referenced, and raw JSON. For a researcher who understands decision trees, this is exactly the right level of detail.

#### F5.2 — No way to compare two policies [MINOR]
**Description:** A researcher would want to compare two policies side-by-side — their decision trees, parameters, and expected behavior. Currently you can only view one at a time.

**Severity:** 🟢 MINOR

#### F5.3 — Decision tree is shown as raw JSON only [MAJOR]
**Description:** The policy detail view shows the full policy as raw JSON in a collapsible section. For a researcher, this is the most important piece — the actual decision logic — but it's presented as a wall of JSON. A visual tree representation would be far more accessible.

**Recommendation:** Add a visual decision tree renderer (boxes and arrows) showing condition nodes, action leaves, and parameter references.

**Severity:** 🟡 MAJOR

---

### 6. Create/Editor Views

#### F6.1 — YAML scenario editor is functional ✓ [POSITIVE]
**Description:** The scenario editor provides templates, live validation via backend API, a summary panel showing parsed parameters, and a "Save & Launch" flow. The EventTimelineBuilder component for visual event scheduling is a nice touch.

#### F6.2 — No syntax highlighting in editors [MINOR]
**Description:** Both YAML (scenario) and JSON (policy) editors are plain `<textarea>` elements with monospace font. No syntax highlighting, line numbers, or error markers. This is fine for quick edits but painful for longer scenarios.

**Severity:** 🟢 MINOR

#### F6.3 — Policy editor has no visual tree builder [MAJOR]
**Description:** Building policy decision trees requires writing raw JSON. The templates help, but constructing a multi-level condition tree by hand is error-prone. A visual node editor (drag-and-drop tree builder) would make this accessible to non-programmers.

**Severity:** 🟡 MAJOR

---

### 7. Game View (from source code analysis)

#### F7.1 — Comprehensive game state display ✓ [POSITIVE]
**Description:** The GameView shows: progress bar, day timeline with optimization markers, per-agent per-day cost breakdowns (liquidity/delay/penalty/total), tick replay with balance animation, fraction evolution chart, cost evolution chart, policy evolution panel with diff support, reasoning panel with bootstrap statistics, and event summaries. This is research-grade output.

#### F7.2 — Streaming AI reasoning is a standout feature ✓ [POSITIVE]
**Description:** During optimization phases, the UI streams the LLM's reasoning text in real-time with a blinking cursor. This gives researchers direct insight into the AI's thought process — something that would be very appealing for auditing and understanding agent behavior.

#### F7.3 — Bootstrap statistics are shown but not explained [MAJOR]
**Description:** The reasoning panel shows `Δ=...`, `CV=...`, `CI=[...]`, `n=...` for each optimization decision. These are critical for evaluating whether policy changes are statistically significant, but there's no explanation of what they mean. A label like "95% CI of cost improvement" would help.

**Severity:** 🟡 MAJOR

#### F7.4 — Balance chart is custom SVG, not interactive [MINOR]
**Description:** The intra-day balance chart (`MiniBalanceChart`) is a custom SVG polyline chart without tooltips, zoom, or hover values. For a researcher, being able to hover over a specific tick to see exact balances is essential.

**Severity:** 🟢 MINOR

#### F7.5 — Policy evolution uses Recharts, balance charts use custom SVG [COSMETIC]
**Description:** The PolicyEvolutionPanel imports Recharts for line charts, while the GameView uses hand-rolled SVG for balance and evolution charts. This inconsistency means different interaction models (Recharts has tooltips; custom SVG doesn't).

**Severity:** 💅 COSMETIC

#### F7.6 — No export functionality for game results [MAJOR]
**Description:** After a multi-day game completes, there's no way to export results as CSV, JSON, or PDF. A researcher needs to export data for analysis in R/Python, include charts in papers, or share results with colleagues.

**Severity:** 🟡 MAJOR

#### F7.7 — "Auto-run" with no speed control [MINOR]
**Description:** The auto-run button runs all remaining days as fast as possible. There's no speed slider or "pause between days" option. For a demo or presentation, being able to run at a measured pace would be useful.

**Severity:** 🟢 MINOR

---

### 8. Documentation

#### F8.1 — Documentation is exceptionally thorough ✓ [POSITIVE]
**Description:** The Docs section contains 14 pages covering: Overview, How the Simulator Works, The Cost Model, AI Policy Optimization, Experiments, Game Theory Primer, Technical Architecture, Scenario System, Policy Decision Trees, LLM Optimization Deep Dive, three blog posts, and References. The content is accurate, well-structured, and written at the right level for a payments researcher. The experiment results (with specific convergence numbers) add credibility.

#### F8.2 — Documentation is embedded in frontend code [MAJOR]
**Description:** All 1,837 lines of documentation are hardcoded in `DocsView.tsx` as React components. This means: (a) docs can't be updated without a frontend deploy, (b) they aren't available outside the web app (e.g., as a standalone site or PDF), (c) they can't be linked to from external publications.

**Recommendation:** Move docs to Markdown files served by the backend or a static site generator. Render in the frontend via markdown-to-React.

**Severity:** 🟡 MAJOR

#### F8.3 — Blog posts are a great idea but need peer context [MINOR]
**Description:** The three blog posts ("Do LLM Agents Converge?", "Financial Stress Tests", "From FIFO to Nash") are well-written analysis pieces. For credibility with central bankers, they should reference the specific BIS working paper more prominently and include comparison tables with the BIS paper's results.

**Severity:** 🟢 MINOR

#### F8.4 — No API documentation [MINOR]
**Description:** The backend has a rich REST API (scenarios, policies, games, validation endpoints) but no documentation visible to users. For researchers who want to script experiments or build on the platform, API docs (even auto-generated FastAPI /docs) would be valuable.

**Severity:** 🟢 MINOR

---

### 9. Auditability & Trust

#### F9.1 — Cost breakdowns per agent per day ✓ [POSITIVE]
**Description:** Each day shows liquidity/delay/penalty costs per agent with totals. This is the minimum viable audit trail for a researcher.

#### F9.2 — Cannot trace individual payment lifecycle [MAJOR]
**Description:** Events are shown as a flat list grouped by day. A researcher cannot select a specific payment and trace its lifecycle: arrival → queue → policy decision → settlement (or delay/penalty). This is the #1 missing auditability feature. In RTGS oversight, being able to trace a single transaction end-to-end is fundamental.

**Recommendation:** Add a payment detail view: click on a payment ID to see its full lifecycle (arrival tick, queue entry, each policy evaluation, settlement tick or penalty).

**Severity:** 🟡 MAJOR

#### F9.3 — Seed is shown but not explorable [MINOR]
**Description:** Each day shows its RNG seed (e.g., `seed=42`), which is great for reproducibility. But there's no "re-run this day with same seed" button or explanation of what seed controls.

**Severity:** 🟢 MINOR

#### F9.4 — No formal validation or benchmark results [MAJOR]
**Description:** A skeptical economist would ask: "How do I know your simulation is correct?" There are no formal validation results comparing SimCash output to known analytical solutions, no comparison with the BIS paper's published results (only narrative claims), and no unit test results shown to users.

**Recommendation:** Add a "Validation" section to docs showing: (a) comparison with BIS Table 3 results, (b) analytical equilibrium verification for simple cases, (c) link to test suite results.

**Severity:** 🟡 MAJOR

---

### 10. Visual & Technical Issues

#### F10.1 — Dark theme is consistent ✓ [POSITIVE]
**Description:** The dark theme (slate-900 backgrounds, slate-300/400 text, sky-400/violet-400 accents) is consistently applied across all components.

#### F10.2 — WebSocket reconnection floods console [MINOR]
**Description:** When a game's WebSocket connection fails (e.g., after backend restart), the client retries every ~1 second with no backoff or maximum retry limit. The console fills with `ERR_CONNECTION_REFUSED` errors. This was observed in the browser console during testing.

**Severity:** 🟢 MINOR

#### F10.3 — Mobile responsive design is present but untested [MINOR]
**Description:** The code includes responsive breakpoints (`md:`, `lg:`, `sm:`) and a mobile nav dropdown in DocsView. Without being able to render the actual UI, I cannot verify proper behavior at mobile breakpoints.

**Severity:** 🟢 MINOR

#### F10.4 — No loading states for some API calls [MINOR]
**Description:** Some views (PolicyEditorView) fetch library data on mount but don't show loading indicators. The `setDetailLoading` state is set but never rendered in ScenarioLibraryView.

**Severity:** 🟢 MINOR

---

### 11. Missing Features a Researcher Would Expect

#### F11.1 — No batch experiment runner [MAJOR]
**Description:** A researcher testing a hypothesis needs to run the same scenario multiple times with different parameters (e.g., varying liquidity cost rates). There's no way to queue multiple runs, compare results across configurations, or run parameter sweeps.

**Severity:** 🟡 MAJOR

#### F11.2 — No data export [MAJOR]
(Covered in F7.6)

#### F11.3 — No scenario comparison view [MINOR]
**Description:** After running two scenarios, there's no way to compare their outcomes side-by-side. A researcher would want to see "Scenario A (2-bank) vs Scenario B (3-bank)" cost trajectories overlaid.

**Severity:** 🟢 MINOR

#### F11.4 — No collaboration features [MINOR]
**Description:** No sharing, no saved game URLs, no team workspaces. This is acceptable for early-stage but would be needed for institutional adoption.

**Severity:** 🟢 MINOR

#### F11.5 — No annotation or note-taking [MINOR]
**Description:** A researcher exploring scenarios would want to annotate findings: "Day 7 shows coordination failure — Bank A exploits Bank B's generous allocation." No way to add notes to game states.

**Severity:** 🟢 MINOR

---

## Recommendations (Prioritized)

### Must Fix (before any external demo)
1. **Add frontend auth bypass for local development** — Check `VITE_AUTH_DISABLED` env var, skip Firebase auth entirely. This is trivial to implement.
2. **Add a landing page** — Before login, show what SimCash does with key features, screenshots, and institutional context.

### Should Fix (before researcher beta)
3. **Visual decision tree renderer** for policy inspection
4. **Payment lifecycle tracing** — click any payment to see its full journey
5. **Data export** — CSV/JSON/PDF for game results, charts, and cost data
6. **Explain bootstrap statistics** — tooltips or inline help for Δ, CV, CI
7. **Explain "LLM Strategy Depth"** — what Simple/Standard/Full mean
8. **Simplify navigation** — reduce to 3-4 top-level sections
9. **Move docs to Markdown files** — enable external linking and non-app access
10. **Add formal validation results** — compare with BIS paper numbers

### Nice to Have (before wider release)
11. Syntax highlighting in YAML/JSON editors
12. Interactive charts with tooltips and hover values
13. Scenario search functionality
14. Batch experiment runner
15. Policy comparison view
16. Scenario comparison view
17. WebSocket reconnection backoff
18. API documentation page

---

## Overall Impression

SimCash is a **genuinely impressive research tool** with deep domain knowledge baked into every aspect — from the Rust simulation engine's determinism guarantees to the nuanced documentation about coordination failures and free-riding in RTGS systems. The architecture (Rust engine + Python orchestration + React frontend) is well-conceived, and the AI policy optimization loop with streaming reasoning is a standout feature that would genuinely excite central bank researchers.

**However, the platform cannot currently be demonstrated to anyone.** The Firebase auth blocker means no one following the local setup instructions can get past the login screen. This needs to be fixed before any evaluation or demo.

Beyond the auth issue, the platform sits at about 70% completion. The core simulation loop works (verified via API), the game view has rich features, and the documentation is publication-quality. What's missing is the "last mile" of UX polish: making the tool trustworthy (auditability, validation), accessible (visual tree rendering, data export), and self-explanatory (better labeling, inline help).

**For a central bank researcher's verdict:** I would be impressed by the depth of the domain model and the documentation. I would be frustrated by not being able to get past the login screen. If I could use it, I would want: (1) payment-level audit trails, (2) formal validation against published results, (3) data export for my own analysis. The "gamification" framing (🎮 icons, "Game" terminology) might not land well in a formal institutional setting — consider offering a "Research Mode" with more academic terminology.

**Grade:** B+ for concept and depth, D for current accessibility.
