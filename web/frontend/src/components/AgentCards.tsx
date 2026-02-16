import type { AgentState } from '../types';

const COLORS: Record<string, string> = {
  BANK_A: 'sky',
  BANK_B: 'violet',
  BANK_C: 'emerald',
  BANK_D: 'amber',
};

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatCost(v: number): string {
  if (v === 0) return '$0.00';
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function AgentCards({ agents }: { agents: Record<string, AgentState> }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Object.entries(agents).map(([id, agent]) => {
        const color = COLORS[id] || 'slate';
        return (
          <div
            key={id}
            className={`rounded-xl border border-slate-700 bg-slate-800/50 p-5 space-y-3`}
          >
            <div className="flex items-center justify-between">
              <h3 className={`font-bold text-${color}-400`}>{id}</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full bg-${color}-500/20 text-${color}-300`}>
                {agent.queue1_size} queued
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Balance</span>
                <span className={`font-mono font-semibold ${agent.balance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatCents(agent.balance)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Available</span>
                <span className="font-mono text-slate-200">{formatCents(agent.available_liquidity)}</span>
              </div>
            </div>

            <div className="border-t border-slate-700 pt-2 space-y-1">
              <div className="text-xs text-slate-500 uppercase tracking-wider">Costs</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <span className="text-slate-400">Liquidity</span>
                <span className="text-right font-mono text-blue-300">{formatCost(agent.costs.liquidity_cost)}</span>
                <span className="text-slate-400">Delay</span>
                <span className="text-right font-mono text-amber-300">{formatCost(agent.costs.delay_cost)}</span>
                <span className="text-slate-400">Penalties</span>
                <span className="text-right font-mono text-red-300">{formatCost(agent.costs.penalty_cost)}</span>
                <span className="text-slate-400 font-semibold">Total</span>
                <span className="text-right font-mono font-semibold text-slate-100">{formatCost(agent.costs.total)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
