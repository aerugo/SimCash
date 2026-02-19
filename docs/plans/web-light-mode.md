# Light Mode — Development Plan

**Status**: In Progress
**Date**: 2026-02-19
**Branch**: feature/interactive-web-sandbox

## Goal

Add an elegant, minimalist light mode with a creamy off-white feel and subtle, sophisticated color choices. Dark mode remains the default. Users toggle via a button in the nav bar. Preference persists in localStorage.

## Design Language (Light Mode)

- **Background**: Creamy off-white `#faf8f5` (warm, not clinical white)
- **Cards/panels**: White `#ffffff` with very subtle warm gray borders `#e8e4df`
- **Text**: Warm charcoal `#2c2825` primary, `#6b6560` secondary
- **Accents**: Muted teal `#3d8b8b` (replaces sky-400), soft violet `#7c6daa` (replaces violet-500)
- **Buttons**: Subtle, low-contrast — soft fills rather than saturated gradients
- **Borders**: Barely visible warm grays, not harsh lines
- **Code blocks**: Light warm gray `#f5f2ee` background
- **Charts**: Same data colors but slightly desaturated for light bg

## Architecture: CSS Custom Properties

Rather than rewriting 1000+ Tailwind classes, we use CSS custom properties that change with a theme class on `<html>`.

### Strategy

1. Define semantic CSS variables for all colors used across the app
2. Set dark values as default (`:root`), light values under `.light`
3. Create a small set of utility classes that reference these variables
4. Migrate components incrementally — highest-impact pages first
5. For Tailwind-native classes like `bg-slate-800/50`, replace with `bg-[var(--surface)]` etc.

### CSS Variables

```css
:root {
  /* Backgrounds */
  --bg-base: #0f172a;
  --bg-surface: #1e293b;
  --bg-surface-hover: #334155;
  --bg-card: #1e293b80;
  --bg-inset: #0f172a80;
  
  /* Text */
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --text-accent: #38bdf8;
  --text-accent-2: #a78bfa;
  
  /* Borders */
  --border: #334155;
  --border-subtle: #1e293b;
  
  /* Interactive */
  --btn-primary: #0284c7;
  --btn-primary-hover: #0369a1;
  --btn-accent: #7c3aed;
  --btn-accent-hover: #6d28d9;
  
  /* Status */
  --success: #4ade80;
  --warning: #fbbf24;
  --danger: #f87171;
}

.light {
  --bg-base: #faf8f5;
  --bg-surface: #ffffff;
  --bg-surface-hover: #f5f2ee;
  --bg-card: #ffffffcc;
  --bg-inset: #f5f2ee;
  
  --text-primary: #2c2825;
  --text-secondary: #6b6560;
  --text-muted: #9b9590;
  --text-accent: #3d8b8b;
  --text-accent-2: #7c6daa;
  
  --border: #e8e4df;
  --border-subtle: #f0ece7;
  
  --btn-primary: #3d8b8b;
  --btn-primary-hover: #327272;
  --btn-accent: #7c6daa;
  --btn-accent-hover: #6b5c99;
  
  --success: #2d8a4e;
  --warning: #b8860b;
  --danger: #c0392b;
}
```

## Phases

| Phase | What | Est. Time |
|-------|------|-----------|
| 1 | CSS variables + theme toggle + body/layout theming | 1h |
| 2 | Core shell: nav, App layout, HomeView, loading states | 1.5h |
| 3 | GameView — the big one (controls, panels, charts) | 2h |
| 4 | DocsView, LibraryViews, ScenarioEditor | 1.5h |
| 5 | Components: modals, tooltips, toast, code editor | 1h |
| 6 | Polish: screenshot review, color tuning, edge cases | 1h |

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/hooks/useTheme.ts` | Theme toggle hook + localStorage persistence |

### Modified (high impact)
| File | Changes |
|------|---------|
| `web/frontend/src/index.css` | CSS variables, `.light` overrides, utility classes |
| `web/frontend/src/App.tsx` | Add theme class to root, render toggle |
| `web/frontend/src/router.tsx` | Shell/layout theme classes |
| All views + components | Migrate hardcoded colors → CSS variables |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `web/backend/` | Theme is purely frontend |

## Iterative Process

Build with dev server running, take screenshots after each phase, evaluate look and feel, adjust colors before moving on. This is a visual task — the screenshot loop is essential.

## Success Criteria

- [ ] Toggle in nav switches between dark and light
- [ ] Light mode feels warm, elegant, minimalist (not clinical/harsh)
- [ ] All text is readable in both modes
- [ ] Charts/graphs look good in both modes
- [ ] Preference persists across page reloads
- [ ] Dark mode is unchanged (no regressions)
- [ ] Frontend compiles and builds clean
