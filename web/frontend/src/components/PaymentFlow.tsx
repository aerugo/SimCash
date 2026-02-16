import type { SimEvent } from '../types';

function s(v: unknown): string { return String(v ?? ''); }
function amt(v: unknown): string { return `$${(Number(v) / 100).toFixed(2)}`; }

export function PaymentFlow({ events, currentTick }: { events: SimEvent[]; currentTick: number }) {
  const tickEvents = events.filter(e => e.tick === currentTick);
  const settlements = tickEvents.filter(e =>
    e.event_type === 'RtgsImmediateSettlement' || e.event_type === 'RtgsQueue2Settle'
  );
  const arrivals = tickEvents.filter(e => e.event_type === 'Arrival');
  const submissions = tickEvents.filter(e => e.event_type === 'RtgsSubmission' || e.event_type === 'PolicySubmit');

  if (tickEvents.length === 0) {
    return <div className="text-slate-500 text-sm italic">No activity this tick.</div>;
  }

  return (
    <div className="space-y-3 text-sm">
      {arrivals.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">📥 Arrivals</div>
          {arrivals.map((ev, i) => (
            <div key={i} className="flex items-center gap-2 py-1 px-2 rounded bg-sky-500/10 text-sky-300">
              <span className="font-mono">{s(ev.sender_id)}</span>
              <span className="text-slate-500">→</span>
              <span className="font-mono">{s(ev.receiver_id)}</span>
              <span className="ml-auto font-mono">{amt(ev.amount)}</span>
            </div>
          ))}
        </div>
      )}

      {submissions.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">📤 Submitted</div>
          {submissions.map((ev, i) => (
            <div key={i} className="flex items-center gap-2 py-1 px-2 rounded bg-green-500/10 text-green-300">
              <span className="font-mono">{s(ev.agent_id || ev.sender)}</span>
              <span className="text-slate-500">→</span>
              <span className="font-mono">{s(ev.receiver || '?')}</span>
              {ev.amount != null && <span className="ml-auto font-mono">{amt(ev.amount)}</span>}
            </div>
          ))}
        </div>
      )}

      {settlements.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">✅ Settled</div>
          {settlements.map((ev, i) => (
            <div key={i} className="flex items-center gap-2 py-1 px-2 rounded bg-emerald-500/10 text-emerald-300">
              <span className="font-mono">{s(ev.sender)}</span>
              <span className="text-slate-500">→</span>
              <span className="font-mono">{s(ev.receiver)}</span>
              <span className="ml-auto font-mono">{amt(ev.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
