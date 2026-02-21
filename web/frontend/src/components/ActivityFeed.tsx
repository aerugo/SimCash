import { useState, useEffect, useRef, useCallback } from 'react';

export type ActivityEventType =
  | 'round_started'
  | 'simulation_running'
  | 'simulation_complete'
  | 'optimization_started'
  | 'agent_thinking'
  | 'agent_done'
  | 'agent_retry'
  | 'agent_fallback'
  | 'round_complete'
  | 'experiment_complete'
  | 'info'
  | 'error';

export type ActivitySeverity = 'info' | 'success' | 'warning' | 'error';

export interface ActivityEvent {
  id: number;
  type: ActivityEventType;
  message: string;
  timestamp: number; // Date.now()
  severity: ActivitySeverity;
  /** If true, this event is "active" (spinner shown) */
  active?: boolean;
}

const SEVERITY_COLORS: Record<ActivitySeverity, string> = {
  info: '#94a3b8',
  success: '#4ade80',
  warning: '#fbbf24',
  error: '#f87171',
};

const ICONS: Record<ActivityEventType, string> = {
  round_started: '🚀',
  simulation_running: '⚙️',
  simulation_complete: '✅',
  optimization_started: '🧠',
  agent_thinking: '💭',
  agent_done: '✓',
  agent_retry: '⚠️',
  agent_fallback: '❌',
  round_complete: '🏁',
  experiment_complete: '🎉',
  info: 'ℹ️',
  error: '❌',
};

function relativeTime(ts: number, now: number): string {
  const diff = Math.max(0, Math.floor((now - ts) / 1000));
  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  const mins = Math.floor(diff / 60);
  const secs = diff % 60;
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s ago` : `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

interface ActivityFeedProps {
  events: ActivityEvent[];
  maxCollapsed?: number;
}

export function ActivityFeed({ events, maxCollapsed = 4 }: ActivityFeedProps) {
  const [expanded, setExpanded] = useState(false);
  const [now, setNow] = useState(Date.now());
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Update relative timestamps every second
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (bottomRef.current && containerRef.current) {
      const el = containerRef.current;
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      if (isNearBottom || !expanded) {
        bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    }
  }, [events.length, expanded]);

  if (events.length === 0) return null;

  const visibleEvents = expanded ? events : events.slice(-maxCollapsed);

  const styles = {
    container: {
      background: 'rgba(30, 41, 59, 0.5)',
      border: '1px solid rgba(71, 85, 105, 0.5)',
      borderRadius: '12px',
      overflow: 'hidden',
      fontSize: '13px',
    } as React.CSSProperties,
    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '8px 12px',
      background: 'rgba(30, 41, 59, 0.8)',
      cursor: 'pointer',
      userSelect: 'none' as const,
    } as React.CSSProperties,
    headerTitle: {
      color: '#94a3b8',
      fontSize: '12px',
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
    } as React.CSSProperties,
    toggle: {
      color: '#64748b',
      fontSize: '11px',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      padding: '2px 6px',
    } as React.CSSProperties,
    list: {
      maxHeight: expanded ? '300px' : `${maxCollapsed * 28 + 8}px`,
      overflowY: 'auto' as const,
      padding: '4px 0',
      transition: 'max-height 0.2s ease',
    } as React.CSSProperties,
    row: (severity: ActivitySeverity, active?: boolean) => ({
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px',
      padding: '3px 12px',
      lineHeight: '22px',
      color: active ? '#e2e8f0' : SEVERITY_COLORS[severity],
      opacity: active ? 1 : 0.85,
    } as React.CSSProperties),
    icon: {
      flexShrink: 0,
      width: '18px',
      textAlign: 'center' as const,
      fontSize: '12px',
    } as React.CSSProperties,
    time: {
      flexShrink: 0,
      fontSize: '10px',
      color: '#475569',
      minWidth: '60px',
      textAlign: 'right' as const,
      paddingTop: '2px',
    } as React.CSSProperties,
    msg: {
      flex: 1,
      whiteSpace: 'pre-wrap' as const,
      wordBreak: 'break-word' as const,
    } as React.CSSProperties,
    pulse: {
      display: 'inline-block',
      width: '6px',
      height: '6px',
      borderRadius: '50%',
      background: '#818cf8',
      marginLeft: '6px',
      animation: 'actfeed-pulse 1.2s ease-in-out infinite',
    } as React.CSSProperties,
  };

  // Inject keyframes once
  const hasStyle = document.getElementById('actfeed-style');
  if (!hasStyle) {
    const style = document.createElement('style');
    style.id = 'actfeed-style';
    style.textContent = `@keyframes actfeed-pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }`;
    document.head.appendChild(style);
  }

  return (
    <div style={styles.container}>
      <div style={styles.header} onClick={() => setExpanded(!expanded)}>
        <div style={styles.headerTitle}>
          <span>📋 Activity</span>
          <span style={{ color: '#475569', fontWeight: 400 }}>({events.length})</span>
          {events.some(e => e.active) && <span style={styles.pulse} />}
        </div>
        <button style={styles.toggle}>
          {expanded ? '▲ Collapse' : `▼ ${events.length > maxCollapsed ? `Show all ${events.length}` : 'Expand'}`}
        </button>
      </div>
      <div ref={containerRef} style={styles.list}>
        {!expanded && events.length > maxCollapsed && (
          <div style={{ textAlign: 'center', padding: '2px 0', fontSize: '10px', color: '#475569' }}>
            … {events.length - maxCollapsed} earlier events
          </div>
        )}
        {visibleEvents.map(evt => (
          <div key={evt.id} style={styles.row(evt.severity, evt.active)}>
            <span style={styles.icon}>{ICONS[evt.type] || '•'}</span>
            <span style={styles.msg}>
              {evt.message}
              {evt.active && <span style={styles.pulse} />}
            </span>
            <span style={styles.time}>{relativeTime(evt.timestamp, now)}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Hook to build activity events from WS messages ──

let _nextId = 1;

export function useActivityLog() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const activeSimRef = useRef<number | null>(null);

  const push = useCallback((type: ActivityEventType, message: string, severity: ActivitySeverity, active?: boolean) => {
    const evt: ActivityEvent = { id: _nextId++, type, message, timestamp: Date.now(), severity, active };
    setEvents(prev => [...prev.slice(-200), evt]); // cap at 200
    return evt.id;
  }, []);

  const deactivate = useCallback((id: number) => {
    setEvents(prev => prev.map(e => e.id === id ? { ...e, active: false } : e));
  }, []);

  const clear = useCallback(() => {
    setEvents([]);
    activeSimRef.current = null;
  }, []);

  return { events, push, deactivate, clear, activeSimRef };
}
