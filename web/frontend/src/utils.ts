/** Format integer cents as dollar string */
export function fmtDollars(cents: number): string {
  if (cents == null) return '—';
  return `$${(cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format a cost value (already in dollars) */
export function fmtCost(v: number): string {
  if (v == null) return '—';
  if (v === 0) return '$0.00';
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Read a CSS custom property value from the document root */
function getCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Agent colors that respect the current theme (read from CSS vars at runtime) */
function getThemedAgentColors(): Record<string, string> {
  const a1 = getCssVar('--agent-1') || '#4A6FA5';
  const a2 = getCssVar('--agent-2') || '#7A6B98';
  const a3 = getCssVar('--agent-3') || '#3D7A55';
  const a4 = getCssVar('--agent-4') || '#B8854A';
  const a5 = getCssVar('--agent-5') || '#A06070';
  return {
    BANK_A: a1,
    BANK_B: a2,
    BANK_C: a3,
    BANK_D: a4,
    BANK_E: a5,
    BANK_F: a1,
    BANK_G: a2,
    BANK_H: a3,
  };
}

/** Lazy-initialized agent colors (re-reads on first access per page load) */
let _cachedAgentColors: Record<string, string> | null = null;
export function getAgentColors(): Record<string, string> {
  if (!_cachedAgentColors) _cachedAgentColors = getThemedAgentColors();
  return _cachedAgentColors;
}
/** Invalidate cache (call after theme switch) */
export function invalidateAgentColors() { _cachedAgentColors = null; }

export const AGENT_COLORS: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_target, prop: string) {
    return getAgentColors()[prop];
  },
  ownKeys() {
    return Object.keys(getAgentColors());
  },
  getOwnPropertyDescriptor(_target, prop: string) {
    const colors = getAgentColors();
    if (prop in colors) return { configurable: true, enumerable: true, value: colors[prop] };
    return undefined;
  },
});

export const AGENT_TW_COLORS: Record<string, string> = {
  BANK_A: 'sky',
  BANK_B: 'violet',
  BANK_C: 'emerald',
  BANK_D: 'amber',
  BANK_E: 'red',
  BANK_F: 'orange',
  BANK_G: 'teal',
  BANK_H: 'fuchsia',
};

export function getAgentColor(id: string, idx: number = 0): string {
  const colors = getAgentColors();
  return colors[id] || Object.values(colors)[idx % Object.values(colors).length];
}
