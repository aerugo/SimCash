import type { SimulationState, SimEvent, AgentReasoning } from '../types';
import { BalanceChart } from '../components/BalanceChart';
import { CostChart } from '../components/CostChart';
import { EventLog } from '../components/EventLog';
import { AgentCards } from '../components/AgentCards';
import { Controls } from '../components/Controls';
import { QueueVisualization } from '../components/QueueVisualization';
import { PaymentFlow } from '../components/PaymentFlow';
import { SimulationSummary } from '../components/SimulationSummary';
import { AgentReasoningPanel } from '../components/AgentReasoningPanel';

interface Props {
  state: SimulationState;
  events: SimEvent[];
  isRunning: boolean;
  speed: number;
  onTick: () => void;
  onRun: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeedChange: (ms: number) => void;
  reasoning?: Record<string, AgentReasoning[]>;
  onNavigateToAgents?: () => void;
}

export function DashboardView({ state, events, isRunning, speed, onTick, onRun, onPause, onReset, onSpeedChange, reasoning, onNavigateToAgents }: Props) {
  return (
    <div className="space-y-6">
      {/* Summary when complete */}
      {state.is_complete && <SimulationSummary state={state} />}

      {/* Controls */}
      <Controls
        isRunning={isRunning}
        isComplete={state.is_complete}
        speed={speed}
        onTick={onTick}
        onRun={onRun}
        onPause={onPause}
        onReset={onReset}
        onSpeedChange={onSpeedChange}
      />

      {/* Agent Cards */}
      <AgentCards
        agents={state.agents}
        balanceHistory={state.balance_history}
        costHistory={state.cost_history}
      />

      {/* Reasoning Preview */}
      {reasoning && Object.keys(reasoning).length > 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
          <AgentReasoningPanel reasoning={reasoning} compact onNavigateToAgents={onNavigateToAgents} />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {state.balance_history && Object.keys(state.balance_history).length > 0 && (
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Bank Balances</h3>
            <BalanceChart history={state.balance_history} />
          </div>
        )}

        {state.cost_history && Object.keys(state.cost_history).length > 0 && (
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Accumulated Costs</h3>
            <CostChart history={state.cost_history} />
          </div>
        )}
      </div>

      {/* Queue + Payment Flow side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Payment Queues</h3>
          <QueueVisualization agents={state.agents} />
        </div>
        <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">
            Tick {state.current_tick > 0 ? state.current_tick - 1 : 0} Activity
          </h3>
          <PaymentFlow events={events} currentTick={state.current_tick > 0 ? state.current_tick - 1 : 0} />
        </div>
      </div>

      {/* Event Log */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">
          Event Log ({events.length} events)
        </h3>
        <EventLog events={events} />
      </div>
    </div>
  );
}
