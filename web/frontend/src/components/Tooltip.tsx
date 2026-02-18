import { useState, useRef, useCallback, type ReactNode } from 'react';

interface TooltipProps {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), 200);
  }, []);

  const hide = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  }, []);

  return (
    <span className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 rounded-lg text-[11px] leading-tight text-white bg-[#1e293b] border border-slate-600 shadow-lg whitespace-nowrap max-w-xs z-50 pointer-events-none"
          style={{ whiteSpace: 'normal', width: 'max-content', maxWidth: '260px' }}
        >
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-[#1e293b]" />
        </span>
      )}
    </span>
  );
}

/** Small inline info icon with tooltip */
export function InfoTip({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-slate-700 text-[9px] text-slate-400 cursor-help ml-1 hover:bg-slate-600 hover:text-slate-300 transition-colors">?</span>
    </Tooltip>
  );
}
