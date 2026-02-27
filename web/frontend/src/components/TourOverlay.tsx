import { useEffect, useState, useCallback, useRef } from 'react';
import type { TourStep } from '../hooks/useTour';
import { TOUR_STEPS, ACT_TRANSITIONS } from '../hooks/useTour';

// ── TourOverlay (main tooltip) ─────────────────────────────────────

interface TourOverlayProps {
  step: number;
  currentStep: TourStep;
  waitingForInteraction: boolean;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function getTargetRect(target: string): Rect | null {
  const el = document.querySelector(`[data-tour="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

type Position = 'top' | 'bottom' | 'left' | 'right';

function pickPosition(rect: Rect, tooltipW: number, tooltipH: number): Position {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const pad = 16;
  if (rect.top + rect.height + tooltipH + pad < vh) return 'bottom';
  if (rect.top - tooltipH - pad > 0) return 'top';
  if (rect.left + rect.width + tooltipW + pad < vw) return 'right';
  return 'left';
}

function getTooltipStyle(rect: Rect, pos: Position, tooltipW: number, tooltipH: number): React.CSSProperties {
  const pad = 12;
  const vw = window.innerWidth;
  let top = 0;
  let left = 0;

  switch (pos) {
    case 'bottom':
      top = rect.top + rect.height + pad + window.scrollY;
      left = rect.left + rect.width / 2 - tooltipW / 2;
      break;
    case 'top':
      top = rect.top - tooltipH - pad + window.scrollY;
      left = rect.left + rect.width / 2 - tooltipW / 2;
      break;
    case 'right':
      top = rect.top + rect.height / 2 - tooltipH / 2 + window.scrollY;
      left = rect.left + rect.width + pad;
      break;
    case 'left':
      top = rect.top + rect.height / 2 - tooltipH / 2 + window.scrollY;
      left = rect.left - tooltipW - pad;
      break;
  }

  if (left < 8) left = 8;
  if (left + tooltipW > vw - 8) left = vw - tooltipW - 8;
  if (top < 8) top = 8;

  return { position: 'absolute', top, left, width: tooltipW };
}

/** Render text with **bold** and *italic* markdown */
function renderBold(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: '#ffffff', fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic">{part.slice(1, -1)}</em>;
    }
    return <span key={i}>{part}</span>;
  });
}

const ACT_NAMES: Record<number, string> = {
  1: 'The Setup',
  2: 'The Disaster',
  3: 'The Recovery',
  4: 'The Deep Dive',
  5: 'The Payoff',
};

export function TourOverlay({ step, currentStep, waitingForInteraction, onNext, onBack, onSkip }: TourOverlayProps) {
  // SVG overlay is always pointer-events:none so users can hover/click spotlighted elements
  const [rect, setRect] = useState<Rect | null>(null);
  const [visible, setVisible] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipSize, setTooltipSize] = useState({ w: 340, h: 200 });

  const updateRect = useCallback(() => {
    const r = getTargetRect(currentStep.target);
    if (r) {
      const el = document.querySelector(`[data-tour="${currentStep.target}"]`);
      if (el) {
        const elRect = el.getBoundingClientRect();
        if (elRect.top < 0 || elRect.bottom > window.innerHeight) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(() => {
            const newR = getTargetRect(currentStep.target);
            if (newR) setRect(newR);
          }, 400);
        }
      }
      setRect(r);
    } else {
      setRect(null);
    }
  }, [currentStep.target]);

  // Handle delay and visibility
  useEffect(() => {
    setVisible(false);
    const delay = currentStep.delay ?? 0;
    const timer = setTimeout(() => {
      updateRect();
      setVisible(true);
    }, delay);
    return () => clearTimeout(timer);
  }, [currentStep, updateRect]);

  useEffect(() => {
    if (!visible) return;
    const handleResize = () => updateRect();
    window.addEventListener('resize', handleResize);
    window.addEventListener('scroll', handleResize, true);
    const timer = setInterval(updateRect, 500);
    const cleanup = setTimeout(() => clearInterval(timer), 5000);
    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('scroll', handleResize, true);
      clearInterval(timer);
      clearTimeout(cleanup);
    };
  }, [visible, updateRect]);

  useEffect(() => {
    if (tooltipRef.current) {
      const r = tooltipRef.current.getBoundingClientRect();
      setTooltipSize({ w: r.width, h: r.height });
    }
  });

  if (!visible) return null;

  // Last step is the completion card — don't show tooltip
  if (currentStep.id === 'whats-next') return null;

  const totalSteps = TOUR_STEPS.length - 1; // exclude completion card step

  // ── Cinematic full-screen slide ──
  if (currentStep.cinematic) {
    const labels = ['The Problem', 'The Insight', 'The Experiment'];
    return (
      <div
        className="fixed inset-0 z-[10001] flex items-center justify-center"
        style={{ backgroundColor: 'rgba(2, 6, 24, 0.95)' }}
      >
        <div
          key={currentStep.id}
          className="max-w-xl px-8 text-center space-y-6"
          style={{ animation: 'cinematic-fade 0.6s ease-out' }}
        >
          {/* Act label */}
          <div className="text-sm font-semibold tracking-[0.35em] uppercase" style={{ color: 'rgba(255,255,255,0.4)' }}>
            {labels[step] ?? ''}
          </div>

          {/* Content */}
          <p className="text-xl leading-relaxed font-light" style={{ color: 'rgba(255,255,255,0.85)' }}>
            {renderBold(currentStep.content)}
          </p>

          {/* Navigation */}
          <div className="flex items-center justify-center gap-4 pt-4">
            {step > 0 && (
              <button
                onClick={onBack}
                className="w-10 h-10 flex items-center justify-center rounded-full text-slate-500 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Back"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
              </button>
            )}
            <button
              onClick={onNext}
              className="px-6 py-2.5 rounded-xl text-sm font-medium bg-sky-500 hover:bg-sky-400 text-white transition-colors"
            >
              {step === 2 ? 'Let\'s go →' : 'Next'}
            </button>
          </div>

          {/* Progress dots */}
          <div className="flex items-center justify-center gap-2 pt-2">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="rounded-full transition-all duration-300"
                style={{
                  width: i === step ? 24 : 6,
                  height: 6,
                  backgroundColor: i === step ? 'rgb(14, 165, 233)' : 'rgba(255,255,255,0.2)',
                }}
              />
            ))}
          </div>

          {/* Skip */}
          <button
            onClick={onSkip}
            className="text-xs transition-colors"
            style={{ color: 'rgba(255,255,255,0.3)' }}
          >
            Skip tour
          </button>
        </div>
      </div>
    );
  }

  const spotPad = 8;
  const pos = rect ? pickPosition(rect, tooltipSize.w, tooltipSize.h) : 'bottom';
  const tooltipStyle = rect
    ? getTooltipStyle(rect, pos, tooltipSize.w, tooltipSize.h)
    : { position: 'fixed' as const, top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: 340 };

  const isInteractive = currentStep.interaction && currentStep.interaction.type !== 'none';
  const showNextButton = !waitingForInteraction;
  const actName = ACT_NAMES[currentStep.act];

  return (
    <>
      {/* Backdrop with cutout */}
      <div className="fixed inset-0 z-[9998]" style={{ pointerEvents: 'none' }}>
        <svg width="100%" height="100%" style={{ position: 'fixed', inset: 0, pointerEvents: 'none' }}>
          <defs>
            <mask id="tour-mask">
              <rect width="100%" height="100%" fill="white" />
              {rect && (
                <rect
                  x={rect.left - spotPad}
                  y={rect.top - spotPad}
                  width={rect.width + spotPad * 2}
                  height={rect.height + spotPad * 2}
                  rx={8}
                  fill="black"
                />
              )}
            </mask>
          </defs>
          <rect
            width="100%" height="100%"
            fill="rgba(2, 6, 23, 0.75)"
            mask="url(#tour-mask)"
            onClick={(e) => e.stopPropagation()}
          />
        </svg>
      </div>

      {/* Spotlight ring */}
      {rect && (
        <div
          className="fixed z-[9999] pointer-events-none rounded-lg ring-2 ring-sky-400/60 ring-offset-2 ring-offset-transparent"
          style={{
            top: rect.top - spotPad,
            left: rect.left - spotPad,
            width: rect.width + spotPad * 2,
            height: rect.height + spotPad * 2,
          }}
        />
      )}

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="z-[10000] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl shadow-sky-500/10 p-4 animate-fade-in"
        style={tooltipStyle}
      >
        {/* Header: act label + step counter + skip */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-sky-400 font-medium">Act {currentStep.act}: {actName}</span>
            <span className="text-[10px] text-slate-600">·</span>
            <span className="text-[10px] text-slate-500 font-mono">{step + 1}/{totalSteps}</span>
          </div>
          <button
            onClick={onSkip}
            className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
          >
            Skip tour
          </button>
        </div>

        {/* Content */}
        <p className="text-sm text-slate-300 leading-relaxed mb-4">
          {renderBold(currentStep.content)}
        </p>

        {/* Interaction hint */}
        {waitingForInteraction && isInteractive && (
          <div className="text-xs text-sky-400/80 mb-3 flex items-center gap-1.5 animate-pulse">
            <span>👆</span>
            <span>
              {currentStep.interaction!.type === 'click-day' && `Click Day ${(currentStep.interaction as { day: number }).day + 1} to continue`}
              {currentStep.interaction!.type === 'open-modal' && 'Click the button to continue'}
              {currentStep.interaction!.type === 'close-modal' && 'Close the modal to continue'}
              {currentStep.interaction!.type === 'expand' && 'Expand the section to continue'}
              {currentStep.interaction!.type === 'click-pill' && 'Click a pill to continue'}
            </span>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={onBack}
            disabled={step === 0}
            className="w-8 h-8 flex items-center justify-center rounded-full text-slate-500 hover:text-white hover:bg-slate-700/60 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
            aria-label="Back"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
          </button>

          {/* Progress bar */}
          <div className="flex-1 mx-3 h-1 bg-slate-700/60 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-500 rounded-full transition-all duration-300"
              style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
            />
          </div>

          {showNextButton && (
            <button
              onClick={onNext}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500 hover:bg-sky-400 text-white transition-colors"
            >
              {step === totalSteps - 1 ? 'Finish' : 'Next'}
            </button>
          )}
        </div>
      </div>
    </>
  );
}

// ── Act Transition Interstitial ────────────────────────────────────

interface ActTransitionProps {
  actNumber: number;
  onDismiss: () => void;
}

export function ActTransition({ actNumber, onDismiss }: ActTransitionProps) {
  const text = ACT_TRANSITIONS[actNumber] ?? '';
  const actName = ACT_NAMES[actNumber] ?? '';

  // Auto-advance after 2s
  useEffect(() => {
    const timer = setTimeout(onDismiss, 2000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div
      className="fixed inset-0 z-[10001] flex items-center justify-center cursor-pointer animate-fade-in"
      style={{ backgroundColor: 'rgba(2, 6, 24, 0.95)' }}
      onClick={onDismiss}
    >
      <div className="text-center space-y-4 px-8">
        <div className="text-sm font-semibold tracking-[0.35em] uppercase" style={{ color: 'rgba(255,255,255,0.4)' }}>Act {actNumber}</div>
        <div className="text-5xl font-bold tracking-tight" style={{ color: '#ffffff' }}>{actName}</div>
        <div className="text-lg italic font-light" style={{ color: 'rgba(255,255,255,0.6)' }}>{text}</div>
      </div>
    </div>
  );
}

// ── Tour Completion Card (v2) ──────────────────────────────────────

export function TourCompletionCard({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center animate-fade-in" style={{ backgroundColor: 'rgba(2, 6, 24, 0.7)' }}>
      <div className="bg-slate-900 border border-sky-500/30 rounded-xl shadow-2xl shadow-sky-500/10 p-6 max-w-md mx-4">
        <h3 className="text-lg font-semibold text-white text-center mb-4">You've seen the full lifecycle.</h3>
        <div className="space-y-3 text-sm text-slate-300 mb-6">
          <div className="flex items-start gap-3">
            <span className="text-lg">🎬</span>
            <span><strong className="text-white">Browse scenarios</strong> in the Library — or create your own</span>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-lg">🧠</span>
            <span><strong className="text-white">Bring your API key</strong> (Settings) to run with GPT, Claude, or Gemini</span>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-lg">🔬</span>
            <span><strong className="text-white">Change the constraint preset</strong> — try "simple" (fraction only) vs "full" (fraction + decision trees)</span>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-lg">📊</span>
            <span><strong className="text-white">Compare runs</strong> — same scenario, different models. See who learns faster.</span>
          </div>
        </div>
        <p className="text-xs text-slate-500 text-center mb-4">Every run produces different strategies. See what emerges.</p>
        <div className="text-center">
          <button
            onClick={onDismiss}
            className="px-6 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-sm font-medium transition-colors"
          >
            Start Exploring
          </button>
        </div>
      </div>
    </div>
  );
}

/** @deprecated kept for backwards compat — replaced by TourCompletionCard */
export function TourCompletionNote({ onDismiss }: { onDismiss: () => void }) {
  return <TourCompletionCard onDismiss={onDismiss} />;
}
