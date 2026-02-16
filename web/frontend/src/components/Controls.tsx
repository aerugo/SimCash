interface ControlsProps {
  isRunning: boolean;
  isComplete: boolean;
  speed: number;
  onTick: () => void;
  onRun: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeedChange: (ms: number) => void;
}

export function Controls({ isRunning, isComplete, speed, onTick, onRun, onPause, onReset, onSpeedChange }: ControlsProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <button
        onClick={onTick}
        disabled={isRunning || isComplete}
        className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-sm transition-colors"
        title="Step (→)"
      >
        ⏭ Step
      </button>

      {!isRunning ? (
        <button
          onClick={onRun}
          disabled={isComplete}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-sm transition-colors"
          title="Play (Space)"
        >
          ▶ Play
        </button>
      ) : (
        <button
          onClick={onPause}
          className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 font-medium text-sm transition-colors"
          title="Pause (Space)"
        >
          ⏸ Pause
        </button>
      )}

      <button
        onClick={onReset}
        className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 font-medium text-sm transition-colors"
        title="Reset (R)"
      >
        ↻ Reset
      </button>

      <div className="flex items-center gap-2 ml-auto">
        <label className="text-xs text-slate-400">Speed:</label>
        <input
          type="range"
          min={50}
          max={2000}
          step={50}
          value={speed}
          onChange={e => onSpeedChange(Number(e.target.value))}
          className="w-28 accent-sky-400"
        />
        <span className="text-xs text-slate-500 w-14">{speed}ms</span>
      </div>

      {isComplete && (
        <span className="ml-2 text-green-400 text-sm font-semibold animate-pulse">✓ Complete</span>
      )}
    </div>
  );
}
