import type { AgentReasoning } from '../types';
import { AgentReasoningPanel } from '../components/AgentReasoningPanel';

interface Props {
  reasoning: Record<string, AgentReasoning[]>;
}

export function AgentsView({ reasoning }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">🧠 Agent Reasoning</h2>
        <p className="text-sm text-slate-400 mt-1">
          Watch AI agents think through liquidity allocation and payment timing decisions in real-time.
        </p>
      </div>
      <AgentReasoningPanel reasoning={reasoning} />
    </div>
  );
}
