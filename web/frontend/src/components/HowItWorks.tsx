import { useState } from 'react';

const SESSION_KEY = 'simcash_how_it_works_dismissed';

interface Props {
  defaultOpen?: boolean;
}

export function HowItWorks({ defaultOpen = false }: Props) {
  const [open, setOpen] = useState(() => {
    const dismissed = sessionStorage.getItem(SESSION_KEY);
    if (dismissed === 'true') return false;
    return defaultOpen;
  });

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (!next) {
      sessionStorage.setItem(SESSION_KEY, 'true');
    }
  };

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 mb-6">
      <div className="flex items-center justify-between p-4">
        <button
          onClick={toggle}
          className="flex-1 flex items-center justify-between text-left"
        >
          <span className="text-sm font-semibold text-slate-300">
            How It Works
          </span>
          <span className="text-slate-500 text-xs">
            {open ? '▲ hide' : '▼ show'}
          </span>
        </button>
      </div>

      {open && (
        <div className="px-4 pb-4 space-y-4 text-sm text-slate-400">
          <div>
            <h4 className="font-medium text-slate-300 mb-1">What This Simulates</h4>
            <p>
              An RTGS (Real-Time Gross Settlement) payment system where banks must decide
              how to handle every incoming payment — release it immediately, hold it for later,
              split it into smaller parts, use credit facilities, or adjust collateral.
              Based on the coordination game model from Castro et al. (2025).
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">What Agents Control</h4>
            <p>
              Each agent builds a <strong>policy</strong> — a set of decision trees that the Rust engine
              executes automatically every tick. A policy controls:
            </p>
            <ul className="mt-2 space-y-1 ml-4">
              <li>
                <strong className="text-slate-300">Per-transaction decisions</strong> — for each payment in the queue,
                the policy tree evaluates conditions (balance, urgency, queue size, counterparty exposure)
                and decides: Release, Hold, Split, ReleaseWithCredit, or Reprioritize.
              </li>
              <li>
                <strong className="text-slate-300">Per-tick budget</strong> — a bank-level tree can set release budgets,
                manage state registers (cross-tick memory), and control macro-level strategy.
              </li>
              <li>
                <strong className="text-slate-300">Collateral management</strong> — dedicated trees for posting
                or withdrawing collateral to manage borrowing capacity.
              </li>
              <li>
                <strong className="text-slate-300">Liquidity allocation</strong> — the fraction of the pool
                to commit at day start (one of many parameters, not the only one).
              </li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">The Optimization Loop</h4>
            <p>
              Each round: (1) The engine runs the policy for all ticks, (2) Costs
              are tallied — liquidity held, delays incurred, deadlines missed, (3) An AI agent
              analyzes results and proposes an improved policy for the next round —
              potentially restructuring the entire decision tree, not just tuning a number.
              Over many rounds, strategies evolve toward equilibrium.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">Cost Tradeoffs</h4>
            <p>
              Three competing costs ranked by severity: <strong>Liquidity cost</strong>{' '}
              <span className="text-slate-500">(r<sub>c</sub>)</span> — proportional to committed
              funds per tick, cheapest. <strong>Delay cost</strong>{' '}
              <span className="text-slate-500">(r<sub>d</sub>)</span> — per cent of unsettled
              payment per tick. <strong>Deadline penalty</strong>{' '}
              <span className="text-slate-500">(r<sub>b</sub>)</span> — flat fee per unsettled
              payment at end of day, most expensive. The constraint r<sub>c</sub> &lt; r<sub>d</sub> &lt; r<sub>b</sub>{' '}
              ensures banks prefer committing liquidity over delaying, and delaying over missing deadlines.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
