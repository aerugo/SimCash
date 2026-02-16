import type { AgentState } from '../types';

export function QueueVisualization({ agents }: { agents: Record<string, AgentState> }) {
  const entries = Object.entries(agents).filter(([, a]) => a.queue1_size > 0);
  if (entries.length === 0) {
    return <div className="text-slate-500 text-sm italic">No pending payments in queue.</div>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([id, agent]) => (
        <div key={id} className="flex items-center gap-3">
          <span className="text-sm font-semibold text-sky-400 w-20">{id}</span>
          <div className="flex gap-1 flex-wrap">
            {Array.from({ length: agent.queue1_size }, (_, i) => (
              <div
                key={i}
                className="w-6 h-6 rounded bg-amber-500/30 border border-amber-500/50 flex items-center justify-center text-[10px] text-amber-300"
              >
                {i + 1}
              </div>
            ))}
          </div>
          <span className="text-xs text-slate-500 ml-auto">{agent.queue1_size} pending</span>
        </div>
      ))}
    </div>
  );
}
