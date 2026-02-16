import { useState } from 'react';
import type { AgentState, CostBreakdown } from '../types';
import { fmtDollars, fmtCost } from '../utils';
import { AgentDetailModal } from './AgentDetailModal';

export function AgentCards({
  agents,
  balanceHistory,
  costHistory,
}: {
  agents: Record<string, AgentState>;
  balanceHistory?: Record<string, number[]>;
  costHistory?: Record<string, CostBreakdown[]>;
}) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(agents).map(([id, agent]) => (
          <div
            key={id}
            onClick={() => setSelectedAgent(id)}
            className="rounded-xl border border-slate-700 bg-slate-800/50 p-5 space-y-3 cursor-pointer hover:border-sky-500/50 hover:bg-slate-800/80 transition-all"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sky-400">{id}</h3>
              <span className="text-xs px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300">
                {agent.queue1_size} queued
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Balance</span>
                <span className={`font-mono font-semibold ${agent.balance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {fmtDollars(agent.balance)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Available</span>
                <span className="font-mono text-slate-200">{fmtDollars(agent.available_liquidity)}</span>
              </div>
            </div>

            <div className="border-t border-slate-700 pt-2 space-y-1">
              <div className="text-xs text-slate-500 uppercase tracking-wider">Costs</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <span className="text-slate-400">Liquidity</span>
                <span className="text-right font-mono text-blue-300">{fmtCost(agent.costs.liquidity_cost)}</span>
                <span className="text-slate-400">Delay</span>
                <span className="text-right font-mono text-amber-300">{fmtCost(agent.costs.delay_cost)}</span>
                <span className="text-slate-400">Penalties</span>
                <span className="text-right font-mono text-red-300">{fmtCost(agent.costs.penalty_cost)}</span>
                <span className="text-slate-400 font-semibold">Total</span>
                <span className="text-right font-mono font-semibold text-slate-100">{fmtCost(agent.costs.total)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {selectedAgent && (
        <AgentDetailModal
          agentId={selectedAgent}
          agent={agents[selectedAgent]}
          balanceHistory={balanceHistory?.[selectedAgent]}
          costHistory={costHistory?.[selectedAgent]}
          onClose={() => setSelectedAgent(null)}
        />
      )}
    </>
  );
}
