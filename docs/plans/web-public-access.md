# Plan: Public Access Without Login

**Size:** Medium (~4-6h)
**Branch:** `feature/interactive-web-sandbox`

## Goal

Make SimCash usable without login. Only actions that consume server resources (real LLM calls) or persist user data should require authentication.

## Current State

- **Frontend:** `App.tsx` gates everything behind `useAuth()` — no `user` → `LandingView` (marketing page only)
- **Backend:** All `/api/games/*` endpoints require `get_current_user` dependency (returns uid)
- **Onboarding tour:** Launches a quick experiment with `simulated_ai: true` — currently requires login
- **Scenario library, docs, create page:** All behind auth wall despite being read-only

## Design

### Access Tiers

| Action | Auth Required? | Notes |
|--------|---------------|-------|
| View landing page | No | Already works |
| Browse docs | No | Read-only |
| Browse scenario library | No | Read-only |
| View scenario editor / create page | No | Read-only exploration |
| Run onboarding tour (simulated AI) | **No** | No LLM cost, ephemeral |
| Run experiment with real LLM | **Yes** | Costs money |
| Save/list experiments (My Experiments) | **Yes** | Per-user persistence |
| Save custom scenarios/policies | **Yes** | Per-user persistence |
| Admin dashboard | **Yes** (admin) | Already gated |

### Key Principle

**Anonymous users get a `guest-{uuid}` uid.** This avoids forking every backend endpoint into auth/no-auth versions. Guest games are ephemeral (no checkpoint persistence) and limited to simulated AI only.

## Implementation

### Phase 1: Backend — Optional Auth Dependency (~1.5h)

**New dependency: `get_optional_user`**

```python
async def get_optional_user(request: Request) -> str:
    """Returns uid if authenticated, else 'guest-{session_id}'."""
    try:
        return await get_current_user(request)
    except HTTPException:
        # Generate stable guest id from a cookie or random
        guest_id = request.cookies.get("simcash_guest")
        if not guest_id:
            guest_id = f"guest-{uuid4().hex[:12]}"
        return guest_id
```

**Endpoint changes:**

| Endpoint | Current | New |
|----------|---------|-----|
| `POST /api/games` | `get_current_user` | `get_optional_user` + enforce `simulated_ai=true` for guests |
| `GET /api/games/{id}` | `get_current_user` | `get_optional_user` |
| `POST /api/games/{id}/step` | `get_current_user` | `get_optional_user` |
| `POST /api/games/{id}/auto` | `get_current_user` | `get_optional_user` |
| `GET /api/games/{id}/days/*/replay` | `get_current_user` | `get_optional_user` |
| `GET /api/games/{id}/policy-history` | `get_current_user` | `get_optional_user` |
| `GET /api/games/{id}/policy-diff` | `get_current_user` | `get_optional_user` |
| `GET /api/games/{id}/download` | `get_current_user` | `get_optional_user` |
| `DELETE /api/games/{id}` | `get_current_user` | `get_optional_user` |
| `GET /api/games` (list) | `get_current_user` | **Keep auth required** |
| `GET /api/games/scenarios` | `get_current_user` | `get_optional_user` |
| `GET /api/scenarios/library` | No auth | Already public |
| `GET /api/scenarios/library/{id}` | No auth | Already public |
| `POST /api/scenarios` | No auth currently | **Add `get_current_user`** (save requires login) |
| `GET /api/models` | `get_current_user` | Remove auth (read-only) |
| WebSocket `/ws/game/{id}` | `get_ws_user` | `get_optional_ws_user` |

**Guest enforcement in `POST /api/games`:**
```python
if uid.startswith("guest-") and not config.simulated_ai:
    raise HTTPException(403, "Login required to run experiments with real AI")
```

**Skip checkpoint persistence for guests:**
```python
if not uid.startswith("guest-"):
    _save_game_checkpoint(game)
```

**Set guest cookie in middleware:**
```python
@app.middleware("http")
async def guest_cookie(request, call_next):
    response = await call_next(request)
    if not request.cookies.get("simcash_guest"):
        response.set_cookie("simcash_guest", f"guest-{uuid4().hex[:12]}", 
                          max_age=86400, httponly=True, samesite="lax")
    return response
```

### Phase 2: Frontend — Remove Auth Gate (~2h)

**`App.tsx` restructure:**

Current: no user → `LandingView` (dead end)
New: no user → same `RouterProvider` but with `user=null` context

```tsx
function AppContent() {
  const { user, loading, signOut } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);

  // ... admin check only if user exists ...

  if (loading) return <LoadingScreen />;

  return (
    <AuthInfoContext.Provider value={{ 
      isAdmin, 
      user,  // null for guests
      userEmail: user?.email ?? '', 
      onSignOut: signOut 
    }}>
      <RouterProvider router={router} />
    </AuthInfoContext.Provider>
  );
}
```

**Router changes:**
- `/` → `HomeView` (always, not `LandingView`)
- `/experiments` → require auth (redirect to login)
- `/admin` → require auth (already)

**New `<RequireAuth>` wrapper component:**
```tsx
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) {
    // Show login modal or redirect
    return <LoginPrompt reason="You need to sign in to access this feature." />;
  }
  return <>{children}</>;
}
```

**Routes using `RequireAuth`:**
```tsx
{ path: 'experiments', element: <RequireAuth><ExperimentsView /></RequireAuth> },
{ path: 'admin', element: <RequireAuth><AdminRoute /></RequireAuth> },
```

**Layout.tsx changes:**
- Show nav links for all pages (docs, library, create, home)
- "My Experiments" nav → show but prompt login on click if guest
- Header: show "Sign In" button instead of user email for guests
- Tour button always visible

**HomeView changes:**
- Quick Tutorial button works for everyone (uses `simulated_ai: true`)
- "Create Experiment" button: if guest, show login prompt; if logged in, proceed
- Remove any auth-dependent conditional rendering

**GameView changes:**
- Works for all users (guests only reach it via simulated AI games)
- "Save" / "My Experiments" links: show login prompt for guests

### Phase 3: Landing Page Merge (~1h)

Merge `LandingView` content into `HomeView` for guests:
- Guest sees: hero section + Quick Tutorial + How It Works + feature cards + "Sign in for full access" CTA
- Logged-in user sees: Quick Tutorial + scenario library cards + My Experiments link + create button

Or simpler: **keep `HomeView` the same for everyone**, just add a subtle "Sign in to save experiments and use real AI" banner for guests.

### Phase 4: Testing & Edge Cases (~0.5h)

- [ ] Guest can load `/`, `/docs`, `/library/scenarios`, `/create`
- [ ] Guest can run Quick Tutorial (simulated AI, tour mode)
- [ ] Guest cannot run real LLM experiment (gets 403 + frontend prompt)
- [ ] Guest cannot access `/experiments` (login prompt)
- [ ] Guest game state is not checkpointed
- [ ] Logged-in user flow unchanged
- [ ] Cookie-based guest ID is stable within session
- [ ] WebSocket works for guest games

## Files Changed

**Backend:**
- `web/backend/app/auth.py` — add `get_optional_user`, `get_optional_ws_user`, guest cookie middleware
- `web/backend/app/main.py` — swap auth dependencies per table above, add guest LLM guard

**Frontend:**
- `web/frontend/src/App.tsx` — remove auth gate, always render router
- `web/frontend/src/router.tsx` — add `RequireAuth` wrapper on protected routes
- `web/frontend/src/Layout.tsx` — show nav for all, sign-in button for guests
- `web/frontend/src/views/HomeView.tsx` — guest banner, tour always available
- `web/frontend/src/views/GameView.tsx` — login prompts on save/persist actions
- `web/frontend/src/AuthInfoContext.ts` — make user optional
- `web/frontend/src/components/LoginPrompt.tsx` — new component (modal or inline)
- `web/frontend/src/hooks/useAuth.ts` — may need `isGuest` helper

## Non-Goals

- Anonymous users don't get rate limiting (future concern)
- No anonymous experiment persistence (they're ephemeral)
- No anonymous custom scenario/policy saving
- Guest cookie cleanup / expiry management
