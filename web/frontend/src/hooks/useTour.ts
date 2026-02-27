import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

/** The pre-loaded completed experiment used by the tutorial */
export const TUTORIAL_GAME_ID = '9af6fa02';

// ── Interaction types ──────────────────────────────────────────────

export type TourInteraction =
  | { type: 'click-day'; day: number }
  | { type: 'open-modal'; target?: string }
  | { type: 'close-modal' }
  | { type: 'expand'; target?: string }
  | { type: 'click-pill' }
  | { type: 'none' };

// ── Step definition ────────────────────────────────────────────────

export interface TourStep {
  id: string;
  act: 1 | 2 | 3 | 4 | 5;
  target: string;
  content: string;
  interaction?: TourInteraction;
  delay?: number;
}

// ── 25-beat script ─────────────────────────────────────────────────

export const TOUR_STEPS: TourStep[] = [
  // ACT I — "The Setup" (5 beats)
  {
    id: 'welcome',
    act: 1,
    target: 'top-bar',
    content: 'Banks in real-time payment systems face a coordination dilemma: **holding liquidity is expensive, but delaying payments risks gridlock.** SimCash asks: can AI agents learn to navigate this tradeoff — and will they find equilibrium?',
  },
  {
    id: 'the-approach',
    act: 1,
    target: 'top-bar',
    content: 'Letting an AI make every payment decision in real time is a non-starter — **you can\'t audit a neural network forward pass, and you can\'t guarantee consistency.** What if instead, the AI optimizes a structured decision tree once per day, and the system executes those rules deterministically?',
  },
  {
    id: 'the-experiment',
    act: 1,
    target: 'top-bar',
    content: 'That\'s what you\'re looking at. Two AI agents each refined a **decision-tree policy** over 10 rounds — auditable rules, not black-box decisions — by analyzing their own daily results. Let\'s see what they learned.',
  },
  {
    id: 'the-players',
    act: 1,
    target: 'model-badge',
    content: '**BANK_A** and **BANK_B**, each running Gemini 2.5 Pro. They\'re **information-isolated** — each bank sees only its own costs and events, never the other\'s strategy.',
  },
  {
    id: 'the-question',
    act: 1,
    target: 'policy-display',
    content: 'Each bank controls two things: **how much liquidity to commit** (the fraction) and **a decision tree** that decides when to release or hold payments. Both started at fraction 0.5 with a trivial tree that releases everything.',
  },
  {
    id: 'explore-timeline',
    act: 1,
    target: 'round-timeline',
    content: 'Each button is a completed day. **🧠** means the AI optimized afterward. Click **Day 1** to start from the beginning.',
    interaction: { type: 'click-day', day: 0 },
  },

  // ACT II — "The Disaster" (5 beats)
  {
    id: 'day1-wasted-capital',
    act: 2,
    target: 'day-costs',
    content: 'Day 1 cost: **99,600** — but look at the breakdown. It\'s *all* opportunity cost. Zero delays, zero penalties. The banks held too much cash doing nothing.',
  },
  {
    id: 'two-reactions',
    act: 2,
    target: 'reasoning',
    content: 'Both AIs saw the waste. BANK_A had a radical idea: **cut liquidity to zero.** BANK_B was more careful: drop to 0.2 and invent an urgency-based decision tree. Expand their reasoning to compare.',
  },
  {
    id: 'see-consequences',
    act: 2,
    target: 'round-timeline',
    content: 'Click **Day 2** to see what happened.',
    interaction: { type: 'click-day', day: 1 },
  },
  {
    id: 'the-crash',
    act: 2,
    target: 'day-costs',
    content: '💥 **301,703** — a 3x increase. BANK_A\'s zero-liquidity gamble caused massive payment failures: 116,623 in delays, 165,000 in penalties. Meanwhile BANK_B\'s smarter tree kept its costs at just 20,080.',
    delay: 500,
  },
  {
    id: 'why-not-worse',
    act: 2,
    target: 'reasoning',
    content: 'After Day 2, most proposals are **✗ Rejected**. The bootstrap test statistically compares proposals against the current policy — it won\'t accept changes that would likely make things worse. That\'s why BANK_A recovered instead of spiraling.',
  },

  // ACT III — "The Recovery" (6 beats)
  {
    id: 'learning-curve',
    act: 3,
    target: 'cost-evolution',
    content: 'Spike on Day 2, then steady decline. **Hover the points** to see each bank\'s costs separately — notice BANK_B was stable while BANK_A recovered.',
  },
  {
    id: 'watch-trees-grow',
    act: 3,
    target: 'round-timeline',
    content: 'Click **Day 4** and look at the policies below. Something interesting happened to the decision trees.',
    interaction: { type: 'click-day', day: 3 },
  },
  {
    id: 'from-nothing-to-strategy',
    act: 3,
    target: 'policy-history',
    content: 'On Day 1, both trees were a single node: "Release everything." By Day 4, BANK_A checks **urgency OR overdue status** first, then checks if it has enough liquidity, and **Holds** if not. Click **🔍 View Policy** on BANK_A to see the full tree.',
    interaction: { type: 'open-modal' },
  },
  {
    id: 'the-decision-tree',
    act: 3,
    target: 'policy-modal',
    content: 'This is the tree the AI evolved through optimization. **Three conditions, three possible actions.** It learned to prioritize urgent payments, check available funds, and hold back when liquidity is tight — all by reasoning about its own results. Close when you\'re done exploring.',
    interaction: { type: 'close-modal' },
  },
  {
    id: 'independent-discovery',
    act: 3,
    target: 'round-timeline',
    content: 'Now click **Day 7**. BANK_B evolved its tree independently — check what it came up with.',
    interaction: { type: 'click-day', day: 6 },
  },
  {
    id: 'convergence-divergence',
    act: 3,
    target: 'policy-history',
    content: 'BANK_B arrived at a **4-deep tree** — it added a balance conservation layer that BANK_A didn\'t. Same problem, same starting point, but the AIs invented **different strategies** that both work. BANK_A checks overdue status; BANK_B checks balance thresholds. Neither can see the other\'s approach.',
  },

  // ACT IV — "The Deep Dive" (6 beats)
  {
    id: 'what-got-rejected',
    act: 4,
    target: 'policy-history',
    content: 'The **Policy History** shows every optimization attempt. Click a **✗** pill — you\'ll see exactly what the AI proposed and why the bootstrap test blocked it. Some rejections changed the tree; others just tweaked the fraction.',
    interaction: { type: 'click-pill' },
  },
  {
    id: 'rejected-policy',
    act: 4,
    target: 'rejected-policy-btn',
    content: 'Click **🚫 View Rejected Policy** to see the tree that was proposed. Compare it to the accepted policy — sometimes the AI simplifies the tree (losing intelligence), sometimes it makes a parameter bet that the stats don\'t support.',
    interaction: { type: 'open-modal' },
  },
  {
    id: 'bootstrap-stats',
    act: 4,
    target: 'bootstrap-stats',
    content: '**Δ** is the expected cost change (negative = worse). **CV** measures reliability. **CI** is the 95% confidence interval. When CI crosses zero, the system can\'t be confident the change helps — so it rejects.',
  },
  {
    id: 'under-the-hood',
    act: 4,
    target: 'prompt-explorer',
    content: 'Expand **🔍 Prompt Explorer** to see the exact prompt the AI received. Each colored block is a section — system instructions, cost data, scenario rules, policy constraints. The token bar shows how the prompt budget is spent.',
  },
  {
    id: 'tick-replay',
    act: 4,
    target: 'replay',
    content: 'For any day, **Load Replay** to step through tick-by-tick. Watch balances rise and fall as payments settle. Like a debugger for the payment system.',
  },
  {
    id: 'payment-trace',
    act: 4,
    target: 'payment-trace',
    content: 'Switch to **Payment Trace** to follow individual payments from arrival to settlement or expiry. This is where you see the decision tree *in action* — which payments got held, which got released.',
  },

  // ACT V — "The Payoff" (4 beats)
  {
    id: 'the-result',
    act: 5,
    target: 'completion-summary',
    content: '**60.8% cost reduction** over 10 rounds. Two AIs independently invented multi-condition payment strategies, found near-optimal liquidity fractions, and drove system costs from 99,600 to 39,028 — without any prior knowledge of payment systems.',
  },
  {
    id: 'your-workspace',
    act: 5,
    target: 'notes',
    content: '**Notes** saves observations to your browser (included in JSON exports). **Export** gives you CSV or JSON with the full policy history, reasoning, and cost data for analysis in R, Python, or Excel.',
  },
  {
    id: 'activity-feed',
    act: 5,
    target: 'activity-feed',
    content: 'During a live experiment, the **Activity Feed** streams everything in real time — simulations running, AI thinking, retries, errors. Color-coded so you can spot problems at a glance.',
  },
  {
    id: 'whats-next',
    act: 5,
    target: 'completion-card',
    content: '',  // Not used — completion card has its own content
  },
];

/** Act transition interstitial text */
export const ACT_TRANSITIONS: Record<number, string> = {
  2: "Let's see what the AI did next…",
  3: 'The AI learned from its mistake.',
  4: "Now let's look at how it thinks.",
  5: 'Time to zoom out.',
};

const STORAGE_KEY = 'simcash_tour_done';

// ── State ──────────────────────────────────────────────────────────

export interface TourState {
  active: boolean;
  step: number;
  act: 1 | 2 | 3 | 4 | 5;
  waitingForInteraction: boolean;
  showCompletion: boolean;
  /** Show act transition interstitial before this act number */
  showActTransition: number | null;
}

export function useTour() {
  const [state, setState] = useState<TourState>({
    active: false,
    step: 0,
    act: 1,
    waitingForInteraction: false,
    showCompletion: false,
    showActTransition: null,
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  const currentStep = useMemo(() => TOUR_STEPS[state.step] ?? null, [state.step]);

  const startTour = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setState({
      active: true,
      step: 0,
      act: 1,
      waitingForInteraction: false,
      showCompletion: false,
      showActTransition: null,
    });
  }, []);

  // Auto-start from URL param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tour') === '1') {
      startTour();
      params.delete('tour');
      const newUrl = params.toString()
        ? `${window.location.pathname}?${params.toString()}`
        : window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [startTour]);

  const advance = useCallback(() => {
    setState(s => {
      if (!s.active) return s;
      const nextIdx = s.step + 1;
      if (nextIdx >= TOUR_STEPS.length) {
        localStorage.setItem(STORAGE_KEY, '1');
        return { ...s, active: false, showCompletion: true, waitingForInteraction: false, showActTransition: null };
      }
      const nextStep = TOUR_STEPS[nextIdx];
      // If next step is the completion card, show completion
      if (nextStep.id === 'whats-next') {
        localStorage.setItem(STORAGE_KEY, '1');
        return { ...s, active: false, showCompletion: true, waitingForInteraction: false, showActTransition: null };
      }
      const currentAct = TOUR_STEPS[s.step].act;
      // Check if we're crossing an act boundary
      if (nextStep.act !== currentAct && ACT_TRANSITIONS[nextStep.act]) {
        return { ...s, showActTransition: nextStep.act, waitingForInteraction: false };
      }
      const hasInteraction = nextStep.interaction && nextStep.interaction.type !== 'none';
      return {
        ...s,
        step: nextIdx,
        act: nextStep.act,
        waitingForInteraction: !!hasInteraction,
        showActTransition: null,
      };
    });
  }, []);

  /** Called when user clicks Next on a tooltip */
  const next = useCallback(() => {
    const s = stateRef.current;
    if (!s.active) return;
    const step = TOUR_STEPS[s.step];
    const hasInteraction = step?.interaction && step.interaction.type !== 'none';
    
    if (hasInteraction && !s.waitingForInteraction) {
      // Enter waiting mode — show the interaction hint, hide Next button
      setState(prev => ({ ...prev, waitingForInteraction: true }));
    } else {
      // No interaction or already completed — advance to next step
      advance();
    }
  }, [advance]);

  const back = useCallback(() => {
    setState(s => {
      if (!s.active || s.step <= 0) return s;
      const prevIdx = s.step - 1;
      return { ...s, step: prevIdx, act: TOUR_STEPS[prevIdx].act, waitingForInteraction: false, showActTransition: null };
    });
  }, []);

  const skip = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setState(s => ({ ...s, active: false, waitingForInteraction: false, showCompletion: false, showActTransition: null }));
  }, []);

  const dismissCompletion = useCallback(() => {
    setState(s => ({ ...s, showCompletion: false }));
  }, []);

  /** Dismiss act transition interstitial and move to the next step */
  const dismissActTransition = useCallback(() => {
    setState(s => {
      if (s.showActTransition === null) return s;
      const nextIdx = s.step + 1;
      if (nextIdx >= TOUR_STEPS.length) {
        localStorage.setItem(STORAGE_KEY, '1');
        return { ...s, active: false, showCompletion: true, showActTransition: null };
      }
      const nextStep = TOUR_STEPS[nextIdx];
      if (nextStep.id === 'whats-next') {
        localStorage.setItem(STORAGE_KEY, '1');
        return { ...s, active: false, showCompletion: true, showActTransition: null };
      }
      const hasInteraction = nextStep.interaction && nextStep.interaction.type !== 'none';
      return {
        ...s,
        step: nextIdx,
        act: nextStep.act,
        waitingForInteraction: !!hasInteraction,
        showActTransition: null,
      };
    });
  }, []);

  /**
   * Notification-based interaction system.
   * Components call this when user performs an action.
   * If the current step expects that interaction, the tour advances.
   */
  const notifyInteraction = useCallback((type: string, detail?: unknown) => {
    const s = stateRef.current;
    if (!s.active || !s.waitingForInteraction) return;
    const step = TOUR_STEPS[s.step];
    if (!step?.interaction) return;

    let matched = false;
    switch (step.interaction.type) {
      case 'click-day':
        if (type === 'day-selected' && detail === step.interaction.day) matched = true;
        break;
      case 'open-modal':
        if (type === 'modal-opened') matched = true;
        break;
      case 'close-modal':
        if (type === 'modal-closed') matched = true;
        break;
      case 'expand':
        if (type === 'section-expanded') matched = true;
        break;
      case 'click-pill':
        if (type === 'pill-clicked') matched = true;
        break;
    }

    if (matched) {
      advance();
    }
  }, [advance]);

  return {
    state,
    currentStep,
    next,
    back,
    skip,
    startTour,
    dismissCompletion,
    dismissActTransition,
    notifyInteraction,
  };
}
