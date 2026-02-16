import type { SimEvent } from '../types';

const EVENT_COLORS: Record<string, string> = {
  arrival: 'text-sky-300',
  policy_submit: 'text-green-300',
  policy_hold: 'text-amber-300',
  rtgs_immediate_settlement: 'text-emerald-300',
  cost_accrual: 'text-slate-400',
  end_of_day: 'text-violet-300',
  scenario_event_executed: 'text-cyan-300',
  deferred_credit_applied: 'text-blue-300',
  transaction_went_overdue: 'text-red-300',
  queue2_liquidity_release: 'text-lime-300',
};

function formatEvent(ev: SimEvent): string {
  const t = ev.event_type;
  if (t === 'arrival') {
    return `📥 Arrival: ${ev.sender_id} → ${ev.receiver_id} $${((ev.amount as number) / 100).toFixed(2)} (deadline: tick ${ev.deadline})`;
  }
  if (t === 'policy_submit') {
    return `📤 Submit: ${ev.agent_id} submits ${ev.tx_id}`;
  }
  if (t === 'policy_hold') {
    return `⏳ Hold: ${ev.agent_id} holds ${ev.tx_id} — ${ev.reason}`;
  }
  if (t === 'rtgs_immediate_settlement') {
    return `✅ Settlement: ${ev.sender} → ${ev.receiver} $${((ev.amount as number) / 100).toFixed(2)}`;
  }
  if (t === 'cost_accrual') {
    const costs = ev.costs as Record<string, number>;
    return `💰 Costs ${ev.agent_id}: liq=${costs?.liquidity_cost?.toFixed(2)} delay=${costs?.delay_cost?.toFixed(2)}`;
  }
  if (t === 'end_of_day') {
    return `🏁 End of Day ${ev.day}: ${ev.unsettled_count} unsettled, penalties=$${ev.total_penalties}`;
  }
  if (t === 'scenario_event_executed') {
    return `⚡ Scenario event: ${ev.scenario_event_type}`;
  }
  if (t === 'deferred_credit_applied') {
    return `💳 Deferred credit: ${ev.agent_id} +$${((ev.amount as number) / 100).toFixed(2)}`;
  }
  if (t === 'transaction_went_overdue') {
    return `⚠️ Overdue: ${ev.tx_id} (${ev.sender_id} → ${ev.receiver_id})`;
  }
  return `${t}: ${JSON.stringify(ev).slice(0, 100)}`;
}

export function EventLog({ events }: { events: SimEvent[] }) {
  if (events.length === 0) {
    return <div className="text-slate-500 text-sm italic">No events yet. Click Step or Play to start.</div>;
  }

  return (
    <div className="max-h-80 overflow-y-auto space-y-0.5 font-mono text-xs">
      {events.map((ev, i) => (
        <div key={i} className={`py-1 px-2 rounded hover:bg-slate-700/50 ${EVENT_COLORS[ev.event_type] || 'text-slate-300'}`}>
          <span className="text-slate-500 mr-2">t={ev.tick}</span>
          {formatEvent(ev)}
        </div>
      ))}
    </div>
  );
}
