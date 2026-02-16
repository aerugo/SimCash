import { useState, useMemo } from 'react';
import type { SimEvent } from '../types';

const EVENT_COLORS: Record<string, string> = {
  Arrival: 'text-sky-300',
  PolicySubmit: 'text-green-300',
  PolicyHold: 'text-amber-300',
  RtgsImmediateSettlement: 'text-emerald-300',
  CostAccrual: 'text-slate-400',
  EndOfDay: 'text-violet-300',
  ScenarioEventExecuted: 'text-cyan-300',
  DeferredCreditApplied: 'text-blue-300',
  TransactionWentOverdue: 'text-red-300',
  Queue2LiquidityRelease: 'text-lime-300',
  RtgsSubmission: 'text-teal-300',
  RtgsQueue2Settle: 'text-indigo-300',
};

const EVENT_ICONS: Record<string, string> = {
  Arrival: '📥',
  PolicySubmit: '📤',
  PolicyHold: '⏳',
  RtgsImmediateSettlement: '✅',
  CostAccrual: '💰',
  EndOfDay: '🏁',
  ScenarioEventExecuted: '⚡',
  DeferredCreditApplied: '💳',
  TransactionWentOverdue: '⚠️',
  RtgsSubmission: '📋',
  RtgsQueue2Settle: '🔄',
};

function fmt$(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatEvent(ev: SimEvent): string {
  const t = ev.event_type;
  const icon = EVENT_ICONS[t] || '•';

  switch (t) {
    case 'Arrival':
      return `${icon} ${ev.sender_id} → ${ev.receiver_id}: ${fmt$(ev.amount as number)} (deadline t=${ev.deadline})`;
    case 'PolicySubmit':
      return `${icon} ${ev.agent_id} submits ${(ev.tx_id as string).slice(0, 8)}…`;
    case 'PolicyHold':
      return `${icon} ${ev.agent_id} holds ${(ev.tx_id as string).slice(0, 8)}… — ${ev.reason}`;
    case 'RtgsImmediateSettlement':
      return `${icon} ${ev.sender} → ${ev.receiver}: ${fmt$(ev.amount as number)}`;
    case 'CostAccrual': {
      const c = ev.costs as Record<string, number> | undefined;
      if (!c) return `${icon} ${ev.agent_id}: costs accrued`;
      return `${icon} ${ev.agent_id}: liq=${c.liquidity_cost?.toFixed(1)} delay=${c.delay_cost?.toFixed(1)} total=${c.total?.toFixed(1)}`;
    }
    case 'EndOfDay':
      return `${icon} End of Day ${ev.day}: ${ev.unsettled_count} unsettled`;
    case 'ScenarioEventExecuted':
      return `${icon} ${ev.scenario_event_type}`;
    case 'DeferredCreditApplied':
      return `${icon} ${ev.agent_id} credited ${fmt$(ev.amount as number)}`;
    case 'TransactionWentOverdue':
      return `${icon} ${(ev.tx_id as string).slice(0, 8)}… overdue (${ev.sender_id} → ${ev.receiver_id})`;
    case 'RtgsSubmission':
      return `${icon} ${ev.sender} → ${ev.receiver}: ${fmt$(ev.amount as number)} submitted to RTGS`;
    case 'RtgsQueue2Settle':
      return `${icon} ${ev.sender} → ${ev.receiver}: ${fmt$(ev.amount as number)} settled from queue`;
    default:
      return `${icon} ${t}`;
  }
}

interface EventLogProps {
  events: SimEvent[];
  fullPage?: boolean;
}

export function EventLog({ events, fullPage = false }: EventLogProps) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [agentFilter, setAgentFilter] = useState<string>('');

  const eventTypes = useMemo(() => [...new Set(events.map(e => e.event_type))], [events]);
  const agentIds = useMemo(() => {
    const ids = new Set<string>();
    events.forEach(ev => {
      if (ev.agent_id) ids.add(ev.agent_id as string);
      if (ev.sender_id) ids.add(ev.sender_id as string);
      if (ev.sender) ids.add(ev.sender as string);
    });
    return [...ids];
  }, [events]);

  const filtered = useMemo(() => {
    return events.filter(ev => {
      if (typeFilter && ev.event_type !== typeFilter) return false;
      if (agentFilter) {
        const hasAgent = [ev.agent_id, ev.sender_id, ev.receiver_id, ev.sender, ev.receiver]
          .some(v => v === agentFilter);
        if (!hasAgent) return false;
      }
      if (search) {
        const text = formatEvent(ev).toLowerCase();
        if (!text.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [events, typeFilter, agentFilter, search]);

  if (events.length === 0) {
    return <div className="text-slate-500 text-sm italic">No events yet. Click Step or Play to start.</div>;
  }

  // Group by tick
  const byTick = new Map<number, SimEvent[]>();
  for (const ev of filtered) {
    const list = byTick.get(ev.tick) || [];
    list.push(ev);
    byTick.set(ev.tick, list);
  }

  return (
    <div className={fullPage ? '' : ''}>
      {/* Filters */}
      <div className="flex gap-2 mb-3 flex-wrap">
        <input
          type="text"
          placeholder="Search events..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 w-48"
        />
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="px-2 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-sky-500"
        >
          <option value="">All Types</option>
          {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select
          value={agentFilter}
          onChange={e => setAgentFilter(e.target.value)}
          className="px-2 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-sky-500"
        >
          <option value="">All Agents</option>
          {agentIds.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <span className="text-xs text-slate-500 self-center ml-auto">{filtered.length}/{events.length} events</span>
      </div>

      <div className={`${fullPage ? 'max-h-[calc(100vh-20rem)]' : 'max-h-80'} overflow-y-auto space-y-2 font-mono text-xs`}>
        {[...byTick.entries()].map(([tick, tickEvents]) => (
          <div key={tick}>
            <div className="text-slate-500 font-semibold text-[10px] uppercase tracking-wider mb-1 sticky top-0 bg-slate-800/90 py-0.5">
              Tick {tick}
            </div>
            {tickEvents.map((ev, i) => (
              <div
                key={`${tick}-${i}`}
                className={`py-0.5 px-2 rounded hover:bg-slate-700/50 ${EVENT_COLORS[ev.event_type] || 'text-slate-300'}`}
              >
                {formatEvent(ev)}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
