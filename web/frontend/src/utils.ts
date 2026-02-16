/** Format integer cents as dollar string */
export function fmtDollars(cents: number): string {
  return `$${(cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format a cost value (already in dollars) */
export function fmtCost(v: number): string {
  if (v === 0) return '$0.00';
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export const AGENT_COLORS: Record<string, string> = {
  BANK_A: '#38bdf8',
  BANK_B: '#a78bfa',
  BANK_C: '#4ade80',
  BANK_D: '#fbbf24',
  BANK_E: '#f87171',
  BANK_F: '#fb923c',
  BANK_G: '#2dd4bf',
  BANK_H: '#e879f9',
};

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
  return AGENT_COLORS[id] || Object.values(AGENT_COLORS)[idx % Object.values(AGENT_COLORS).length];
}
