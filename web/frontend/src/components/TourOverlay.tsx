import { useEffect, useState, useCallback, useRef } from 'react';
import type { TourStep } from '../hooks/useTour';
import { TOUR_STEPS } from '../hooks/useTour';

interface TourOverlayProps {
  step: number;
  currentStep: TourStep;
  waitingForRound: boolean;
  waitingForAuto: boolean;
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

  // Prefer bottom if space
  if (rect.top + rect.height + tooltipH + pad < vh) return 'bottom';
  // Then top
  if (rect.top - tooltipH - pad > 0) return 'top';
  // Then right
  if (rect.left + rect.width + tooltipW + pad < vw) return 'right';
  // Left
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

  // Clamp horizontal
  if (left < 8) left = 8;
  if (left + tooltipW > vw - 8) left = vw - tooltipW - 8;
  // Clamp vertical
  if (top < 8) top = 8;

  return { position: 'absolute', top, left, width: tooltipW };
}

/** Render text with **bold** markdown */
function renderBold(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

export function TourOverlay({ step, currentStep, waitingForRound, waitingForAuto, onNext, onBack, onSkip }: TourOverlayProps) {
  const [rect, setRect] = useState<Rect | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipSize, setTooltipSize] = useState({ w: 340, h: 200 });

  const updateRect = useCallback(() => {
    const r = getTargetRect(currentStep.target);
    if (r) {
      // Scroll into view if needed
      const el = document.querySelector(`[data-tour="${currentStep.target}"]`);
      if (el) {
        const elRect = el.getBoundingClientRect();
        if (elRect.top < 0 || elRect.bottom > window.innerHeight) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          // Re-measure after scroll
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

  useEffect(() => {
    updateRect();
    const handleResize = () => updateRect();
    window.addEventListener('resize', handleResize);
    window.addEventListener('scroll', handleResize, true);
    // Poll briefly for elements that render async
    const timer = setInterval(updateRect, 500);
    const cleanup = setTimeout(() => clearInterval(timer), 5000);
    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('scroll', handleResize, true);
      clearInterval(timer);
      clearTimeout(cleanup);
    };
  }, [updateRect, step]);

  useEffect(() => {
    if (tooltipRef.current) {
      const r = tooltipRef.current.getBoundingClientRect();
      setTooltipSize({ w: r.width, h: r.height });
    }
  });

  // If waiting for user action, hide overlay
  if (waitingForRound || waitingForAuto) return null;

  const spotPad = 8;
  const totalSteps = TOUR_STEPS.length;
  const pos = rect ? pickPosition(rect, tooltipSize.w, tooltipSize.h) : 'bottom';
  const tooltipStyle = rect ? getTooltipStyle(rect, pos, tooltipSize.w, tooltipSize.h) : { position: 'fixed' as const, top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: 340 };

  return (
    <>
      {/* Backdrop with cutout */}
      <div className="fixed inset-0 z-[9998]" style={{ pointerEvents: 'none' }}>
        <svg width="100%" height="100%" style={{ position: 'fixed', inset: 0, pointerEvents: 'auto' }}>
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
        className="z-[10000] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl shadow-sky-500/10 p-4"
        style={tooltipStyle}
      >
        {/* Step counter */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-slate-500 font-mono">{step + 1} of {totalSteps}</span>
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

          <button
            onClick={onNext}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500 hover:bg-sky-400 text-white transition-colors"
          >
            {currentStep.waitForRound ? 'OK' :
             currentStep.waitForAuto ? 'OK' :
             step === totalSteps - 1 ? 'Finish' : 'Next'}
          </button>
        </div>
      </div>
    </>
  );
}

/** Post-tour completion note about simulated vs real AI */
export function TourCompletionNote({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-slate-950/60">
      <div className="bg-slate-900 border border-violet-500/30 rounded-xl shadow-2xl shadow-violet-500/10 p-6 max-w-md mx-4">
        <div className="text-2xl mb-3 text-center">💡</div>
        <p className="text-sm text-slate-300 leading-relaxed text-center mb-4">
          This experiment used <strong className="text-white">simulated AI</strong> for instant results. Real experiments use an LLM (like Gemini) which takes 10–40 seconds per optimization round — but produces genuinely novel strategies.
        </p>
        <div className="text-center">
          <button
            onClick={onDismiss}
            className="px-6 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
          >
            Got it!
          </button>
        </div>
      </div>
    </div>
  );
}
