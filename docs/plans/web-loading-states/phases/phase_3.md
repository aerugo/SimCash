# Phase 3: Frontend — Per-Agent Status Badges

**Status**: Pending

---

## Objective

Show per-agent status badges that indicate what each agent is doing: idle, simulating, "thinking..." (LLM call in progress), or done.

---

## Invariants Enforced in This Phase

- INV-GAME-2: Agent Isolation — each badge reflects only that agent's status

---

## TDD Steps

### Step 3.1: Create AgentStatusBadge Component (GREEN)

**Create `web/frontend/src/components/AgentStatusBadge.tsx`:**

```tsx
type AgentPhase = 'idle' | 'simulating' | 'thinking' | 'done';

interface Props {
  agentId: string;
  phase: AgentPhase;
  elapsed?: number;  // seconds since phase started
}

const phaseStyles: Record<AgentPhase, { label: string; color: string; animate: boolean }> = {
  idle: { label: 'Idle', color: 'bg-gray-700 text-gray-400', animate: false },
  simulating: { label: 'Simulating...', color: 'bg-yellow-800 text-yellow-300', animate: true },
  thinking: { label: 'Thinking...', color: 'bg-blue-800 text-blue-300', animate: true },
  done: { label: 'Done', color: 'bg-green-800 text-green-300', animate: false },
};

export function AgentStatusBadge({ agentId, phase, elapsed }: Props) {
  const style = phaseStyles[phase];

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${style.color}`}>
      {/* Agent name */}
      <span className="font-mono text-sm font-semibold">{agentId}</span>

      {/* Status */}
      <span className={`text-xs ${style.animate ? 'animate-pulse' : ''}`}>
        {style.label}
      </span>

      {/* Thinking dots animation */}
      {phase === 'thinking' && (
        <span className="flex gap-0.5">
          {[0, 1, 2].map(i => (
            <span
              key={i}
              className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </span>
      )}

      {/* Elapsed time for active phases */}
      {(phase === 'thinking' || phase === 'simulating') && elapsed != null && elapsed > 0 && (
        <span className="text-xs opacity-60">{Math.floor(elapsed)}s</span>
      )}
    </div>
  );
}
```

### Step 3.2: Track Per-Agent Status in WS Hook

**Update `web/frontend/src/hooks/useGameWebSocket.ts`:**

```typescript
interface GameWSState {
  // ...existing fields...
  agentStatuses: Record<string, { phase: AgentPhase; startTime: number | null }>;
}

// In message handler:
case 'optimization_start':
  return {
    ...s,
    currentPhase: 'optimizing',
    optimizingAgent: msg.agent_id ?? null,
    agentStatuses: {
      ...s.agentStatuses,
      ...(msg.agent_id ? { [msg.agent_id]: { phase: 'thinking', startTime: msg.timestamp ?? Date.now() / 1000 } } : {}),
    },
  };
case 'optimization_complete':
  return {
    ...s,
    agentStatuses: {
      ...s.agentStatuses,
      ...(msg.agent_id ? { [msg.agent_id]: { phase: 'done', startTime: null } } : {}),
    },
  };
case 'simulation_start':
  return {
    ...s,
    currentPhase: 'simulating',
    agentStatuses: Object.fromEntries(
      Object.keys(s.agentStatuses).map(aid => [aid, { phase: 'simulating', startTime: msg.timestamp ?? Date.now() / 1000 }])
    ),
  };
```

### Step 3.3: Wire Badges into GameView

```tsx
import { AgentStatusBadge } from './AgentStatusBadge';

// Agent status row
<div className="flex gap-2 flex-wrap">
  {gameState?.agent_ids.map(aid => (
    <AgentStatusBadge
      key={aid}
      agentId={aid}
      phase={agentStatuses[aid]?.phase ?? 'idle'}
    />
  ))}
</div>
```

### Step 3.4: Refactor

- Reset all agents to 'idle' on day_complete
- Add tooltip with phase history

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/AgentStatusBadge.tsx` | Create | Per-agent status indicator |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Modify | Track agentStatuses |
| `web/frontend/src/components/GameView.tsx` | Modify | Wire badges |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Each agent has a visible status badge
- [ ] Badge changes: idle → simulating → thinking → done
- [ ] Thinking phase has animated dots
- [ ] Elapsed time shown for active phases
- [ ] Status resets between days
- [ ] TypeScript compiles cleanly
