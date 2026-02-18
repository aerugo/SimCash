# URL Routing — Development Plan

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox

## Goal

Replace in-memory tab state (`useState<TabId>`) with proper URL-based routing so every page has a shareable, bookmarkable URL. Users can link directly to specific scenarios, policies, experiments, and docs pages.

## Current State

- Navigation is purely in-memory: `const [tab, setTab] = useState<TabId>('home')`
- No URL changes when navigating between sections
- Refreshing the page always returns to the home/play view
- No way to link to a specific scenario, policy, or experiment
- No browser back/forward support

## Proposed URL Structure

```
/                           → Home / Run (play section)
/library                    → Library → Scenarios (default sub-tab)
/library/scenarios          → Scenario library
/library/scenarios/:id      → Scenario detail view
/library/policies           → Policy library
/library/policies/:id       → Policy detail view
/create                     → Create (scenario/policy editor)
/experiment/:gameId         → Active experiment view
/experiment/:gameId/round/:day → Specific round of an experiment
/docs                       → Docs overview
/docs/:slug                 → Specific docs page (e.g. /docs/game-theory-primer)
/admin                      → Admin dashboard
```

### URL Design Decisions

1. **`/experiment/:gameId`** not `/game/:gameId` — consistent with Research mode terminology
2. **`/library/scenarios/:id`** not `/scenarios/:id` — keeps Library as the parent context
3. **`/docs/:slug`** — slug maps to markdown file name (already have 17 files with names like `overview.md`, `game-theory-primer.md`)
4. **No hash routing** — use proper path routing with HTML5 History API
5. **Catch-all fallback** — unknown paths redirect to `/` (SPA pattern)

## Web Invariants

- **WEB-INV-5**: Auth gate still applies — unauthenticated users see landing page on all routes
- **WEB-INV-7**: Relative URLs — all API calls remain relative, routing is frontend-only

## Technology Choice

**React Router v7** (`react-router-dom`) — the standard. Minimal bundle impact, well-documented, supports nested routes.

Alternative considered: manual `window.location` + `popstate` — too much boilerplate for nested routes and params.

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/router.tsx` | Route definitions, layout component |

### Modified
| File | Changes |
|------|---------|
| `web/frontend/src/App.tsx` | Replace `useState<TabId>` with `<RouterProvider>`. Extract layout into `Layout` component. Remove manual tab state management. |
| `web/frontend/src/views/HomeView.tsx` | `onNavigate` calls become `<Link>` or `useNavigate()` |
| `web/frontend/src/views/GameView.tsx` | Read `gameId` from URL params instead of props |
| `web/frontend/src/views/ScenarioLibraryView.tsx` | Scenario cards link to `/library/scenarios/:id` |
| `web/frontend/src/views/PolicyLibraryView.tsx` | Policy cards link to `/library/policies/:id` |
| `web/frontend/src/views/DocsView.tsx` | Doc sidebar links to `/docs/:slug`, read slug from params |
| `web/frontend/src/components/GameSettingsPanel.tsx` | "Start Experiment" navigates to `/experiment/:id` after creation |
| `web/frontend/src/api.ts` | No changes (already uses relative URLs) |
| `web/frontend/src/types.ts` | Remove `TabId`, `SectionId`, `NavSection` if fully replaced by routes |
| `web/backend/app/main.py` | Catch-all route: serve `index.html` for all non-`/api` paths (SPA fallback) |
| `web/frontend/vite.config.ts` | Possibly no changes (proxy already handles `/api`) |
| `Dockerfile` | Possibly no changes (already serves static frontend) |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only, don't change |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Install react-router, create route definitions, replace App.tsx tab state with router | 3h | 5 tests |
| 2 | Wire all views to URL params (game ID, scenario ID, policy ID, doc slug) | 2h | 4 tests |
| 3 | Backend SPA fallback + verify Docker build | 1h | 2 tests |

## Phase 1: Router Foundation

### Install
```bash
cd web/frontend && npm install react-router-dom
```

### Create `router.tsx`
Define routes:
```tsx
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomeView /> },
      { path: 'library', element: <LibraryLayout />,
        children: [
          { index: true, element: <Navigate to="scenarios" replace /> },
          { path: 'scenarios', element: <ScenarioLibraryView /> },
          { path: 'scenarios/:scenarioId', element: <ScenarioLibraryView /> },
          { path: 'policies', element: <PolicyLibraryView /> },
          { path: 'policies/:policyId', element: <PolicyLibraryView /> },
        ]
      },
      { path: 'create', element: <CreateView /> },
      { path: 'experiment/:gameId', element: <GameView /> },
      { path: 'docs', element: <DocsView /> },
      { path: 'docs/:slug', element: <DocsView /> },
      { path: 'admin', element: <AdminDashboard /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
```

### Refactor `App.tsx`
- Extract the header/nav bar into a `Layout` component that uses `<NavLink>` for section navigation
- Replace `{tab === 'home' && <HomeView .../>}` conditional rendering with `<Outlet />`
- Game state (WebSocket, gameId) moves to a context or stays in Layout and passes down via Outlet context
- Active section highlighting uses `useLocation()` instead of manual tab state

### Tests
- `tsc -b` passes
- `npm run build` passes
- Backend tests still pass (289)
- Navigation between all sections works
- Browser back/forward works
- Direct URL access works (e.g., opening `/library/scenarios` directly)

## Phase 2: View Integration

### `GameView.tsx`
- Read `gameId` from `useParams()` instead of props
- If no active game for that ID, show "Experiment not found" or redirect home
- "New Experiment" button navigates to `/`

### `ScenarioLibraryView.tsx`
- Scenario cards are `<Link to={`/library/scenarios/${s.id}`}>` 
- If `:scenarioId` param present, auto-open detail panel for that scenario
- "Run this scenario" navigates to `/` with scenario pre-selected (or creates game and navigates to `/experiment/:id`)

### `PolicyLibraryView.tsx`
- Policy cards are `<Link to={`/library/policies/${p.id}`}>`
- If `:policyId` param present, auto-open detail panel

### `DocsView.tsx`
- Sidebar links are `<NavLink to={`/docs/${slug}`}>`
- Read active doc from `useParams().slug`
- Default to `overview` if no slug

### `HomeView.tsx`
- "Explore Scenarios" card links to `/library/scenarios`
- "Policy Library" card links to `/library/policies`
- "Documentation" card links to `/docs`
- "Build Your Own" card links to `/create`
- After game creation, navigate to `/experiment/:gameId`

### Tests
- Direct URL `/library/scenarios/2bank_12tick` opens with that scenario selected
- Direct URL `/docs/game-theory-primer` opens that doc page
- Direct URL `/experiment/abc123` shows experiment (or "not found")
- All internal links produce correct URLs

## Phase 3: Backend SPA Fallback + Docker

### Backend (`main.py`)
The backend already serves static files. Need to ensure all non-API paths serve `index.html`:

```python
# Catch-all: serve frontend for SPA routing
@app.get("/{path:path}")
async def serve_spa(path: str):
    # If path starts with 'api/' or 'ws/', let other handlers handle it
    # Otherwise serve index.html
    ...
```

Verify this works in Docker build (where static files are in `/app/static/`).

### Tests
- `curl https://staging/library/scenarios` returns `index.html` (not 404)
- `curl https://staging/experiment/abc123` returns `index.html`
- `curl https://staging/api/health` still returns JSON (not index.html)
- Docker build succeeds

## Success Criteria

- [ ] Every page has a unique, bookmarkable URL
- [ ] Browser back/forward works correctly
- [ ] Direct URL access works (paste URL → correct page loads)
- [ ] Sharing a URL to a specific scenario/policy/doc works
- [ ] All 289 backend tests pass
- [ ] `tsc -b` and `npm run build` pass
- [ ] Docker build succeeds
- [ ] No regressions in existing functionality

## UI Test Protocol

```
Protocol: URL Routing
Wave: URL Routing

1. Open https://simcash-997004209370.europe-north1.run.app/?dev_token=...
2. VERIFY: URL is / and home page shows
3. Click "Library" in nav
4. VERIFY: URL is /library/scenarios
5. Click a scenario card (e.g., "2 Banks, 12 Ticks")
6. VERIFY: URL is /library/scenarios/2bank_12tick and detail panel is open
7. Copy URL, open in new tab
8. VERIFY: Same scenario detail is shown
9. Click browser Back
10. VERIFY: URL is /library/scenarios, no scenario selected
11. Click "Policies" sub-tab
12. VERIFY: URL is /library/policies
13. Click "Docs" in nav
14. VERIFY: URL is /docs or /docs/overview
15. Click "Game Theory Primer" in sidebar
16. VERIFY: URL is /docs/game-theory-primer
17. Click "Run" in nav
18. VERIFY: URL is /
19. Start an experiment (Quick Start)
20. VERIFY: URL changes to /experiment/<gameId>
21. Refresh the page
22. VERIFY: Experiment view reloads (may show "Experiment not found" if in-memory — acceptable for now)
23. Navigate to /nonexistent-path
24. VERIFY: Redirected to /

PASS if all VERIFY steps succeed.
```
