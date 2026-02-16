# Phase 6: Polish

**Status**: Pending
**Started**: —

## Objective

Production-quality UX: keyboard shortcuts, error handling, responsive layout, notifications.

## Implementation Steps

### Step 6.1: Keyboard Shortcuts
- `Space` — play/pause
- `→` / `Right Arrow` — step one tick
- `R` — reset
- `1-7` — switch tabs
- `Escape` — close modals
- Show shortcut hints in UI (small "?" tooltip)

### Step 6.2: Toast Notifications
Create `src/components/Toast.tsx`:
- Success: "Simulation created", "Simulation complete"
- Error: "Failed to create simulation", "WebSocket disconnected"
- Info: "AI agents thinking..."
- Auto-dismiss after 3s, stack multiple

### Step 6.3: Error Handling
- Error boundaries around each view
- API error display (not just console.log)
- WebSocket reconnection on disconnect
- Loading spinners during API calls

### Step 6.4: Responsive Layout
- Tab bar collapses to hamburger on mobile
- Charts resize properly
- Agent cards stack vertically on narrow screens
- Min-width: 768px (tablet)

### Step 6.5: Visual Polish
- Professional SimCash header with subtle gradient
- Consistent spacing and typography
- Smooth transitions between tabs
- Active state animations on buttons

## Files

| File | Action |
|------|--------|
| `src/components/Toast.tsx` | CREATE |
| `src/hooks/useKeyboardShortcuts.ts` | CREATE |
| `src/hooks/useToast.ts` | CREATE |
| `src/App.tsx` | MODIFY — integrate shortcuts + toasts |
| `src/index.css` | MODIFY — responsive breakpoints |

## Completion Criteria
- [ ] All keyboard shortcuts work
- [ ] Toast notifications appear for key actions
- [ ] Errors shown to user, not swallowed
- [ ] Layout works on 768px+ screens
- [ ] No visual jank or layout shifts
