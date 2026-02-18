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
            💡 How It Works
          </span>
          <span className="text-slate-500 text-xs">
            {open ? '▲ hide' : '▼ show'}
          </span>
        </button>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            className="ml-3 text-xs text-sky-400 hover:text-sky-300 transition-colors"
          >
            ℹ️ How it works
          </button>
        )}
      </div>

      {open && (
        <div className="px-4 pb-4 space-y-4 text-sm text-slate-400">
          <div>
            <h4 className="font-medium text-slate-300 mb-1">🏦 What This Simulates</h4>
            <p>
              An RTGS (Real-Time Gross Settlement) payment system where banks must decide
              how much liquidity to commit each day. Banks face a strategic tradeoff:
              commit more liquidity (costly) or risk payment delays and penalties.
              Based on the coordination game model from Castro et al. (2025).
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">🔄 The Game Loop</h4>
            <p>
              Each day: (1) Banks commit liquidity based on their policy, (2) Payments
              arrive (stochastically or on a fixed schedule) and settle in real-time, (3) Costs
              are tallied — liquidity held, delays incurred, deadlines missed, (4) An AI agent
              analyzes each bank's results and proposes an improved policy for the next day.
              Over many days, policies converge toward a stable profile.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">🎯 Key Parameter</h4>
            <p>
              <code className="text-xs bg-slate-900 px-1 py-0.5 rounded text-sky-400">
                initial_liquidity_fraction
              </code>{' '}
              — the fraction of a bank's liquidity pool to commit at the start of each day.
              0% = commit nothing (payments will fail), 100% = commit everything (expensive).
              The AI optimizes this value, typically converging around 5–10% for standard scenarios.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">⚖️ Cost Tradeoffs</h4>
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
