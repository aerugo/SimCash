import { useState, useEffect } from 'react';
import type { PaymentTrace, PaymentTraceResponse } from '../types';
import { getPaymentTraces } from '../api';

interface Props {
  gameId: string;
  dayNum: number;
}

const STATUS_CONFIG = {
  settled: { icon: '✅', label: 'Settled', color: 'text-green-400', bg: 'bg-green-500/10' },
  delayed: { icon: '⏳', label: 'Delayed', color: 'text-amber-400', bg: 'bg-amber-500/10' },
  failed:  { icon: '❌', label: 'Failed',  color: 'text-red-400',   bg: 'bg-red-500/10' },
} as const;

const EVENT_COLORS: Record<string, string> = {
  Arrival: 'text-sky-400',
  RtgsSubmission: 'text-slate-400',
  PolicySubmit: 'text-slate-500',
  RtgsImmediateSettlement: 'text-green-400',
  BilateralOffset: 'text-green-400',
  CycleSettlement: 'text-green-400',
  QueuedRtgs: 'text-amber-400',
  Hold: 'text-amber-400',
  Release: 'text-sky-300',
  DeadlineMiss: 'text-red-400',
  EodPenalty: 'text-red-400',
  DeferredCreditApplied: 'text-violet-400',
};

export function PaymentTraceView({ gameId, dayNum }: Props) {
  const [data, setData] = useState<PaymentTraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'settled' | 'delayed' | 'failed'>('all');

  useEffect(() => {
    setLoading(true);
    setError(null);
    getPaymentTraces(gameId, dayNum)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [gameId, dayNum]);

  if (loading) return <div className="text-sm text-slate-400 animate-pulse p-4">Loading payment traces…</div>;
  if (error) return <div className="text-sm text-red-400 p-4">Error: {error}</div>;
  if (!data) return null;

  const filtered = filter === 'all' ? data.payments : data.payments.filter(p => p.status === filter);

  const counts = { settled: 0, delayed: 0, failed: 0 };
  for (const p of data.payments) counts[p.status]++;

  return (
    <div className="space-y-3">
      {/* Summary bar */}
      <div className="flex items-center gap-3 text-xs">
        <span className="text-slate-400">{data.total_payments} payments</span>
        <button onClick={() => setFilter('all')} className={`px-2 py-0.5 rounded ${filter === 'all' ? 'bg-slate-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}>All</button>
        {(['settled', 'delayed', 'failed'] as const).map(s => (
          <button key={s} onClick={() => setFilter(s)} className={`px-2 py-0.5 rounded flex items-center gap-1 ${filter === s ? STATUS_CONFIG[s].bg + ' ' + STATUS_CONFIG[s].color : 'text-slate-500 hover:text-slate-300'}`}>
            {STATUS_CONFIG[s].icon} {counts[s]}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-700">
              <th className="text-left py-1.5 px-2 w-8">#</th>
              <th className="text-left py-1.5 px-2">From</th>
              <th className="text-left py-1.5 px-2">To</th>
              <th className="text-right py-1.5 px-2">Amount</th>
              <th className="text-right py-1.5 px-2">Arrived</th>
              <th className="text-right py-1.5 px-2">Settled</th>
              <th className="text-left py-1.5 px-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <PaymentRow
                key={p.tx_id}
                payment={p}
                expanded={expandedId === p.tx_id}
                onToggle={() => setExpandedId(expandedId === p.tx_id ? null : p.tx_id)}
              />
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center text-slate-600 text-xs py-4">No payments match filter</div>
        )}
      </div>
    </div>
  );
}

function PaymentRow({ payment: p, expanded, onToggle }: { payment: PaymentTrace; expanded: boolean; onToggle: () => void }) {
  const cfg = STATUS_CONFIG[p.status];

  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-slate-800 hover:bg-slate-800/50 cursor-pointer transition-colors"
      >
        <td className="py-1.5 px-2 text-slate-500 font-mono">{p.index + 1}</td>
        <td className="py-1.5 px-2 font-mono text-sky-300">{p.sender ?? '—'}</td>
        <td className="py-1.5 px-2 font-mono text-violet-300">{p.receiver ?? '—'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-emerald-400">
          {p.amount != null ? `$${(p.amount / 100).toLocaleString()}` : '—'}
        </td>
        <td className="py-1.5 px-2 text-right font-mono text-slate-400">{p.arrival_tick ?? '—'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-slate-400">{p.settled_tick ?? '—'}</td>
        <td className="py-1.5 px-2">
          <span className={`${cfg.color} flex items-center gap-1`}>
            {cfg.icon} {cfg.label}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="bg-slate-900/70 px-4 py-3">
            <div className="text-[10px] text-slate-500 mb-2 font-mono">
              tx_id: {p.tx_id}
              {p.deadline_tick != null && <span className="ml-3">deadline: tick {p.deadline_tick}</span>}
              {p.settlement_type && <span className="ml-3">via {p.settlement_type}</span>}
            </div>
            <div className="relative pl-4 border-l-2 border-slate-700 space-y-1.5">
              {p.lifecycle.map((e, i) => {
                const color = EVENT_COLORS[e.event_type] ?? 'text-slate-400';
                return (
                  <div key={i} className="flex items-start gap-2">
                    <div className="absolute -left-[5px] w-2 h-2 rounded-full bg-slate-600 mt-1" style={{ top: `${i * 28 + 4}px` }} />
                    <span className="font-mono text-slate-600 w-8 text-right shrink-0">t{e.tick}</span>
                    <span className={`font-medium ${color}`}>{e.event_type}</span>
                    <span className="text-slate-600 truncate">
                      {formatDetails(e.details)}
                    </span>
                  </div>
                );
              })}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function formatDetails(details: Record<string, unknown>): string {
  const parts: string[] = [];
  if (details.amount != null) parts.push(`$${(Number(details.amount) / 100).toLocaleString()}`);
  if (details.sender_id) parts.push(`${details.sender_id}`);
  if (details.sender && !details.sender_id) parts.push(`${details.sender}`);
  if (details.receiver_id) parts.push(`→ ${details.receiver_id}`);
  if (details.receiver && !details.receiver_id) parts.push(`→ ${details.receiver}`);
  if (details.sender_balance_before != null) {
    parts.push(`bal: $${(Number(details.sender_balance_before) / 100).toLocaleString()} → $${(Number(details.sender_balance_after) / 100).toLocaleString()}`);
  }
  return parts.join(' · ');
}
