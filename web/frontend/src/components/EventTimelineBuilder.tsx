import { useState, useMemo, useCallback } from 'react';
import type { EventTimelineBuilderProps, ScenarioEvent, EventType } from '../types';
import { EVENT_TYPES } from '../types';

// ── colours per event type ──────────────────────────────────────────
const EVENT_COLORS: Record<EventType, string> = {
  DirectTransfer: '#f472b6',        // pink-400
  GlobalArrivalRateChange: '#38bdf8', // sky-400
  AgentArrivalRateChange: '#a78bfa', // violet-400
  DeadlineWindowChange: '#facc15',   // yellow-400
  CollateralAdjustment: '#34d399',   // emerald-400
};

const EVENT_LABELS: Record<EventType, string> = {
  DirectTransfer: 'Direct Transfer',
  GlobalArrivalRateChange: 'Global Arrival Rate',
  AgentArrivalRateChange: 'Agent Arrival Rate',
  DeadlineWindowChange: 'Deadline Window',
  CollateralAdjustment: 'Collateral Adj.',
};

// ── param field definitions ─────────────────────────────────────────
interface FieldDef {
  key: string;
  label: string;
  type: 'number' | 'agent';
}

const PARAM_FIELDS: Record<EventType, FieldDef[]> = {
  DirectTransfer: [
    { key: 'from_agent', label: 'From Agent', type: 'agent' },
    { key: 'to_agent', label: 'To Agent', type: 'agent' },
    { key: 'amount', label: 'Amount', type: 'number' },
  ],
  GlobalArrivalRateChange: [
    { key: 'multiplier', label: 'Rate Multiplier', type: 'number' },
  ],
  AgentArrivalRateChange: [
    { key: 'agent', label: 'Agent', type: 'agent' },
    { key: 'multiplier', label: 'Rate Multiplier', type: 'number' },
  ],
  DeadlineWindowChange: [
    { key: 'min_ticks_multiplier', label: 'Min Ticks Multiplier', type: 'number' },
    { key: 'max_ticks_multiplier', label: 'Max Ticks Multiplier', type: 'number' },
  ],
  CollateralAdjustment: [
    { key: 'agent', label: 'Agent', type: 'agent' },
    { key: 'delta', label: 'Delta (±cents)', type: 'number' },
  ],
};

let _idCounter = 0;
function nextId(): string {
  return `evt_${Date.now()}_${_idCounter++}`;
}

// ── helpers for YAML conversion ─────────────────────────────────────
export function eventsToYaml(events: ScenarioEvent[]): string {
  if (events.length === 0) return '';
  const lines: string[] = ['scenario_events:'];
  for (const ev of events) {
    lines.push(`  - type: ${ev.type}`);
    // Emit params as flat fields (engine-compatible format)
    for (const [k, v] of Object.entries(ev.params)) {
      lines.push(`    ${k}: ${v}`);
    }
    // Emit schedule (not trigger)
    lines.push(`    schedule:`);
    if (ev.trigger.type === 'OneTime') {
      lines.push(`      type: OneTime`);
      lines.push(`      tick: ${ev.trigger.tick}`);
    } else {
      lines.push(`      type: Repeating`);
      lines.push(`      start_tick: ${ev.trigger.start_tick}`);
      lines.push(`      interval: ${ev.trigger.interval}`);
    }
  }
  return lines.join('\n');
}

export function yamlToEvents(yamlEvents: unknown[]): ScenarioEvent[] {
  if (!Array.isArray(yamlEvents)) return [];
  return yamlEvents.map((raw) => {
    const rawObj = raw as Record<string, unknown>;
    const trigger = rawObj.trigger as Record<string, unknown> | undefined;
    const schedule = rawObj.schedule as Record<string, unknown> | undefined;
    const trig = trigger || schedule;
    let parsedTrigger: ScenarioEvent['trigger'];
    if (trig && trig.type === 'Repeating') {
      parsedTrigger = {
        type: 'Repeating',
        start_tick: Number(trig.start_tick ?? 0),
        interval: Number(trig.interval ?? 1),
      };
    } else {
      parsedTrigger = {
        type: 'OneTime',
        tick: Number(trig?.tick ?? 0),
      };
    }
    const params: Record<string, unknown> = {};
    const rawParams = rawObj.params as Record<string, unknown> | undefined;
    if (rawParams) {
      Object.assign(params, rawParams);
    } else {
      // legacy flat format
      const reserved = new Set(['type', 'trigger', 'schedule']);
      for (const [k, v] of Object.entries(rawObj)) {
        if (!reserved.has(k)) params[k] = v;
      }
    }
    return {
      id: nextId(),
      type: rawObj.type as EventType,
      trigger: parsedTrigger,
      params,
    };
  });
}

// ── default params for a new event ──────────────────────────────────
function defaultParams(type: EventType, agentIds: string[]): Record<string, unknown> {
  const a = agentIds[0] ?? 'BANK_A';
  const b = agentIds[1] ?? agentIds[0] ?? 'BANK_B';
  switch (type) {
    case 'DirectTransfer': return { from_agent: a, to_agent: b, amount: 100000 };
    case 'GlobalArrivalRateChange': return { multiplier: 1.5 };
    case 'AgentArrivalRateChange': return { agent: a, multiplier: 1.5 };
    case 'DeadlineWindowChange': return { min_ticks_multiplier: 1.0, max_ticks_multiplier: 1.0 };
    case 'CollateralAdjustment': return { agent: a, delta: 50000 };
  }
}

// ── component ───────────────────────────────────────────────────────
export function EventTimelineBuilder({ events, agentIds, totalTicks, onChange }: EventTimelineBuilderProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // form state
  const [formType, setFormType] = useState<EventType>('DirectTransfer');
  const [formTriggerType, setFormTriggerType] = useState<'OneTime' | 'Repeating'>('OneTime');
  const [formTick, setFormTick] = useState(0);
  const [formStartTick, setFormStartTick] = useState(0);
  const [formInterval, setFormInterval] = useState(10);
  const [formParams, setFormParams] = useState<Record<string, unknown>>(() => defaultParams('DirectTransfer', agentIds));

  const resetForm = useCallback((evt?: ScenarioEvent) => {
    if (evt) {
      setFormType(evt.type);
      setFormTriggerType(evt.trigger.type);
      if (evt.trigger.type === 'OneTime') {
        setFormTick(evt.trigger.tick);
      } else {
        setFormStartTick(evt.trigger.start_tick);
        setFormInterval(evt.trigger.interval);
      }
      setFormParams({ ...evt.params });
    } else {
      setFormType('DirectTransfer');
      setFormTriggerType('OneTime');
      setFormTick(0);
      setFormStartTick(0);
      setFormInterval(10);
      setFormParams(defaultParams('DirectTransfer', agentIds));
    }
  }, [agentIds]);

  const handleSave = useCallback(() => {
    const trigger: ScenarioEvent['trigger'] =
      formTriggerType === 'OneTime'
        ? { type: 'OneTime', tick: formTick }
        : { type: 'Repeating', start_tick: formStartTick, interval: formInterval };

    if (editingId) {
      onChange(events.map(e => e.id === editingId ? { ...e, type: formType, trigger, params: { ...formParams } } : e));
      setEditingId(null);
    } else {
      onChange([...events, { id: nextId(), type: formType, trigger, params: { ...formParams } }]);
    }
    setShowForm(false);
  }, [editingId, events, formType, formTriggerType, formTick, formStartTick, formInterval, formParams, onChange]);

  const handleDelete = useCallback((id: string) => {
    onChange(events.filter(e => e.id !== id));
    if (editingId === id) { setEditingId(null); setShowForm(false); }
  }, [events, editingId, onChange]);

  const handleEdit = useCallback((evt: ScenarioEvent) => {
    setEditingId(evt.id);
    resetForm(evt);
    setShowForm(true);
  }, [resetForm]);

  const handleAdd = useCallback(() => {
    setEditingId(null);
    resetForm();
    setShowForm(true);
  }, [resetForm]);

  // compute tick positions for markers
  const markers = useMemo(() => {
    const result: { id: string; tick: number; type: EventType; label: string; repeating: boolean }[] = [];
    for (const ev of events) {
      if (ev.trigger.type === 'OneTime') {
        result.push({ id: ev.id, tick: ev.trigger.tick, type: ev.type, label: formatEventLabel(ev), repeating: false });
      } else {
        // show first 20 repeating occurrences
        for (let t = ev.trigger.start_tick; t <= totalTicks && result.length < events.length * 20 + 100; t += ev.trigger.interval) {
          result.push({ id: ev.id, tick: t, type: ev.type, label: formatEventLabel(ev) + ` (tick ${t})`, repeating: true });
        }
      }
    }
    return result;
  }, [events, totalTicks]);

  const setParam = (key: string, value: unknown) => setFormParams(p => ({ ...p, [key]: value }));

  return (
    <div className="rounded-xl p-4 space-y-4" style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)' }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>⚡ Scenario Events</h3>
        <button
          onClick={handleAdd}
          className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium transition-colors"
        >
          + Add Event
        </button>
      </div>

      {/* ── Timeline ─────────────────────────────────────── */}
      <div className="relative h-16 rounded-lg overflow-hidden" style={{ background: 'var(--surface-bg, var(--card-bg))', border: '1px solid var(--border-color)' }}>
        {/* tick labels */}
        {totalTicks > 0 && [0, 0.25, 0.5, 0.75, 1].map(frac => {
          const tick = Math.round(frac * totalTicks);
          return (
            <span key={frac} className="absolute bottom-1 text-[10px] transform -translate-x-1/2"
              style={{ left: `${frac * 100}%`, color: 'var(--text-muted)' }}>{tick}</span>
          );
        })}
        {/* markers */}
        {markers.map((m, i) => {
          const pct = totalTicks > 0 ? (m.tick / totalTicks) * 100 : 0;
          return (
            <div key={`${m.id}-${i}`}
              className="absolute top-2 w-3 h-3 rounded-full border border-slate-900 cursor-pointer hover:scale-150 transition-transform group"
              style={{
                left: `calc(${pct}% - 6px)`,
                backgroundColor: EVENT_COLORS[m.type],
                opacity: m.repeating ? 0.6 : 1,
              }}
              onClick={() => {
                const ev = events.find(e => e.id === m.id);
                if (ev) handleEdit(ev);
              }}
            >
              <div className="hidden group-hover:block absolute bottom-5 left-1/2 -translate-x-1/2 rounded px-2 py-1 text-[10px] whitespace-nowrap z-50 shadow-lg" style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}>
                {m.label}
              </div>
            </div>
          );
        })}
        {events.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-xs" style={{ color: 'var(--text-muted)' }}>No events — click "Add Event" to begin</div>
        )}
      </div>

      {/* ── Legend ────────────────────────────────────────── */}
      {events.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {Array.from(new Set(events.map(e => e.type))).map(t => (
            <span key={t} className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-secondary)' }}>
              <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: EVENT_COLORS[t] }} />
              {EVENT_LABELS[t]}
            </span>
          ))}
        </div>
      )}

      {/* ── Event list ───────────────────────────────────── */}
      {events.length > 0 && (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {events.map(ev => (
            <div key={ev.id}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors"
              style={{
                background: editingId === ev.id ? 'var(--surface-bg, rgba(0,0,0,0.1))' : 'var(--card-bg)',
                border: editingId === ev.id ? '1px solid var(--text-accent)' : '1px solid transparent',
              }}
              onClick={() => handleEdit(ev)}
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: EVENT_COLORS[ev.type] }} />
              <span className="font-medium w-28 truncate" style={{ color: 'var(--text-primary)' }}>{EVENT_LABELS[ev.type]}</span>
              <span className="w-24" style={{ color: 'var(--text-muted)' }}>
                {ev.trigger.type === 'OneTime' ? `tick ${ev.trigger.tick}` : `every ${ev.trigger.interval} from ${ev.trigger.start_tick}`}
              </span>
              <span className="flex-1 truncate" style={{ color: 'var(--text-muted)' }}>{formatParams(ev)}</span>
              <button
                onClick={e => { e.stopPropagation(); handleDelete(ev.id); }}
                className="text-red-400/60 hover:text-red-400 transition-colors px-1"
                title="Delete event"
              >✕</button>
            </div>
          ))}
        </div>
      )}

      {/* ── Add / Edit form ──────────────────────────────── */}
      {showForm && (
        <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>{editingId ? 'Edit Event' : 'New Event'}</h4>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {/* Event type */}
            <div>
              <label className="text-[10px] block mb-1" style={{ color: "var(--text-muted)" }}>Type</label>
              <select value={formType}
                onChange={e => {
                  const t = e.target.value as EventType;
                  setFormType(t);
                  setFormParams(defaultParams(t, agentIds));
                }}
                className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }}>
                {EVENT_TYPES.map(t => <option key={t} value={t}>{EVENT_LABELS[t]}</option>)}
              </select>
            </div>

            {/* Trigger type */}
            <div>
              <label className="text-[10px] block mb-1" style={{ color: "var(--text-muted)" }}>Trigger</label>
              <select value={formTriggerType}
                onChange={e => setFormTriggerType(e.target.value as 'OneTime' | 'Repeating')}
                className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }}>
                <option value="OneTime">One-Time</option>
                <option value="Repeating">Repeating</option>
              </select>
            </div>

            {/* Trigger params */}
            {formTriggerType === 'OneTime' ? (
              <div>
                <label className="text-[10px] block mb-1" style={{ color: "var(--text-muted)" }}>Tick</label>
                <input type="number" min={0} max={totalTicks} value={formTick}
                  onChange={e => setFormTick(Number(e.target.value))}
                  className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }} />
              </div>
            ) : (
              <>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: "var(--text-muted)" }}>Start Tick</label>
                  <input type="number" min={0} max={totalTicks} value={formStartTick}
                    onChange={e => setFormStartTick(Number(e.target.value))}
                    className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }} />
                </div>
                <div>
                  <label className="text-[10px] block mb-1" style={{ color: "var(--text-muted)" }}>Interval</label>
                  <input type="number" min={1} value={formInterval}
                    onChange={e => setFormInterval(Number(e.target.value))}
                    className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }} />
                </div>
              </>
            )}
          </div>

          {/* Dynamic param fields */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {PARAM_FIELDS[formType].map(field => (
              <div key={field.key}>
                <label className="text-[10px] block mb-1" style={{ color: 'var(--text-muted)' }}>{field.label}</label>
                {field.type === 'agent' ? (
                  <select value={String(formParams[field.key] ?? '')}
                    onChange={e => setParam(field.key, e.target.value)}
                    className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }}>
                    {agentIds.map(id => <option key={id} value={id}>{id}</option>)}
                    {agentIds.length === 0 && <option value="">No agents</option>}
                  </select>
                ) : (
                  <input type="number" value={Number(formParams[field.key] ?? 0)}
                    onChange={e => setParam(field.key, Number(e.target.value))}
                    className="w-full rounded px-2 py-1.5 text-xs" style={{ background: "var(--input-bg, var(--card-bg))", border: "1px solid var(--border-color)", color: "var(--text-primary)" }} />
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={handleSave}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-medium transition-colors">
              {editingId ? 'Update' : 'Add'}
            </button>
            <button onClick={() => { setShowForm(false); setEditingId(null); }}
              className="px-4 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── formatting helpers ──────────────────────────────────────────────
function formatEventLabel(ev: ScenarioEvent): string {
  const parts = [EVENT_LABELS[ev.type]];
  if (ev.params.amount) parts.push(`$${Number(ev.params.amount).toLocaleString()}`);
  if (ev.params.delta) parts.push(`Δ${Number(ev.params.delta).toLocaleString()}`);
  if (ev.params.multiplier) parts.push(`×${ev.params.multiplier}`);
  if (ev.params.from_agent) parts.push(`${ev.params.from_agent}→${ev.params.to_agent ?? '?'}`);
  else if (ev.params.agent) parts.push(String(ev.params.agent));
  return parts.join(' · ');
}

function formatParams(ev: ScenarioEvent): string {
  return Object.entries(ev.params).map(([k, v]) => `${k}=${v}`).join(', ');
}
