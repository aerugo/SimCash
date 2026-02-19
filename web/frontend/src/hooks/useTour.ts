import { useState, useEffect, useCallback, useMemo } from 'react';

export interface TourStep {
  target: string;          // data-tour attribute value
  content: string;         // tooltip text (supports **bold**)
  phase: 1 | 2 | 3;
  waitForRound?: boolean;  // step 8: hide overlay, wait for round 1
  waitForAuto?: boolean;   // step 15: wait for auto to start
}

export const TOUR_STEPS: TourStep[] = [
  // Phase 1: Interface Overview
  { target: 'top-bar', phase: 1, content: 'Welcome! This is the experiment runner. You\'ll watch AI agents learn to optimize payment strategies over multiple rounds. The counter shows your progress.' },
  { target: 'next-btn', phase: 1, content: 'Click **Next** to run one round at a time. Each round simulates a full day of interbank payments.' },
  { target: 'rerun-btn', phase: 1, content: '**Re-run** replays the last round with the same random seed — useful for verifying results are deterministic.' },
  { target: 'auto-btn', phase: 1, content: '**Auto** runs all remaining rounds automatically. Use the speed control to adjust pacing — fast skips the pause between rounds.' },
  { target: 'export-btn', phase: 1, content: 'Export your results as **CSV** or **JSON** for further analysis in R, Python, or Excel.' },
  { target: 'progress-bar', phase: 1, content: 'This tracks how many rounds have completed out of the total.' },
  { target: 'empty-state', phase: 1, content: 'Each agent starts with an initial liquidity policy. The AI optimizer will refine it after each round based on observed costs.' },
  { target: 'next-btn', phase: 1, content: 'Let\'s run the first round! Click **▶ Next** to begin.', waitForRound: true },
  // Phase 2: First Round Results
  { target: 'round-timeline', phase: 2, content: 'Each numbered button is a completed round. Click any to review its results. The 🧠 icon means the AI optimized policies after that round.' },
  { target: 'day-costs', phase: 2, content: 'This is the cost breakdown — liquidity cost (holding money), delay cost (slow payments), and penalties (missed deadlines). The settlement rate shows what percentage of payments cleared.' },
  { target: 'balance-chart', phase: 2, content: 'Watch how each bank\'s balance moves tick-by-tick through the day. Dips mean outgoing payments; rises mean incoming.' },
  { target: 'cost-evolution', phase: 2, content: 'This chart tracks total system cost across rounds. With good optimization, you should see costs trend downward.' },
  { target: 'reasoning', phase: 2, content: 'After each round, the AI analyzes what went wrong and proposes policy changes. You can expand to read its full reasoning.' },
  { target: 'policy-display', phase: 2, content: 'The current policy for each agent — showing the liquidity fraction (how much of their pool to commit) and the decision tree (when to release or hold payments).' },
  // Phase 3: Auto-run & Advanced
  { target: 'auto-btn', phase: 3, content: 'Now let\'s see the AI learn! Click **⏩ Auto** to run the remaining rounds automatically.', waitForAuto: true },
  { target: 'replay', phase: 3, content: 'After any round, click **Load Replay** to step through tick-by-tick — see exactly which payments settled and when.' },
  { target: 'payment-trace', phase: 3, content: 'The **Payment Trace** shows every individual payment\'s lifecycle — when it arrived, queued, settled, or expired.' },
  { target: 'notes', phase: 3, content: 'Use the **Notes** panel to jot down observations. When the experiment completes, you\'ll see a summary with total cost reduction. That\'s the tour — happy experimenting! 🎉' },
];

const STORAGE_KEY = 'simcash_tour_done';

export interface TourState {
  active: boolean;
  step: number;
  phase: 1 | 2 | 3;
  waitingForRound: boolean;
  waitingForAuto: boolean;
  showCompletion: boolean;
}

export function useTour(daysCount: number, autoRunning: boolean) {
  const [state, setState] = useState<TourState>({
    active: false,
    step: 0,
    phase: 1,
    waitingForRound: false,
    waitingForAuto: false,
    showCompletion: false,
  });

  const currentStep = useMemo(() => TOUR_STEPS[state.step] ?? null, [state.step]);

  // Start tour (e.g. from ?tour=1)
  const startTour = useCallback(() => {
    setState({ active: true, step: 0, phase: 1, waitingForRound: false, waitingForAuto: false, showCompletion: false });
  }, []);

  // Auto-start from URL param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tour') === '1') {
      const done = localStorage.getItem(STORAGE_KEY);
      if (!done) {
        startTour();
      }
      // Remove ?tour=1 from URL without reload
      params.delete('tour');
      const newUrl = params.toString()
        ? `${window.location.pathname}?${params.toString()}`
        : window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [startTour]);

  // When waiting for round and daysCount increases, advance
  useEffect(() => {
    if (state.waitingForRound && daysCount >= 1) {
      setState(s => ({ ...s, step: 8, phase: 2, waitingForRound: false }));
    }
  }, [state.waitingForRound, daysCount]);

  // When waiting for auto and autoRunning starts, advance
  useEffect(() => {
    if (state.waitingForAuto && autoRunning) {
      setState(s => ({ ...s, step: s.step + 1, waitingForAuto: false }));
    }
  }, [state.waitingForAuto, autoRunning]);

  const next = useCallback(() => {
    setState(s => {
      if (!s.active) return s;
      const step = TOUR_STEPS[s.step];
      if (step?.waitForRound) {
        return { ...s, waitingForRound: true };
      }
      if (step?.waitForAuto) {
        return { ...s, waitingForAuto: true };
      }
      const nextIdx = s.step + 1;
      if (nextIdx >= TOUR_STEPS.length) {
        localStorage.setItem(STORAGE_KEY, '1');
        return { ...s, active: false, showCompletion: true };
      }
      return { ...s, step: nextIdx, phase: TOUR_STEPS[nextIdx].phase };
    });
  }, []);

  const back = useCallback(() => {
    setState(s => {
      if (!s.active || s.step <= 0) return s;
      const prevIdx = s.step - 1;
      return { ...s, step: prevIdx, phase: TOUR_STEPS[prevIdx].phase };
    });
  }, []);

  const skip = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setState(s => ({ ...s, active: false, waitingForRound: false, waitingForAuto: false, showCompletion: false }));
  }, []);

  const dismissCompletion = useCallback(() => {
    setState(s => ({ ...s, showCompletion: false }));
  }, []);

  return { state, currentStep, next, back, skip, startTour, dismissCompletion };
}
