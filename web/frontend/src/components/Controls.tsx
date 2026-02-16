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
    <div className="flex items-center gap-3 flex-wrap">
      <button
        onClick={onTick}
        disabled={isRunning || isComplete}
        className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-sm transition-colors"
      >
        ⏭ Step
      </button>

      {!isRunning ? (
        <button
          onClick={onRun}
          disabled={isComplete}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-sm transition-colors"
        >
          ▶ Play
        </button>
      ) : (
        <button
          onClick={onPause}
          className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 font-medium text-sm transition-colors"
        >
          ⏸ Pause
        </button>
      )}

      <button
        onClick={onReset}
        className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 font-medium text-sm transition-colors"
      >
        ↻ Reset
      </button>

      <div className="flex items-center gap-2 ml-4">
        <label className="text-xs text-slate-400">Speed:</label>
        <input
          type="range"
          min={50}
          max={2000}
          step={50}
          value={speed}
          onChange={e => onSpeedChange(Number(e.target.value))}
          className="w-24 accent-sky-400"
        />
        <span className="text-xs text-slate-500 w-14">{speed}ms</span>
      </div>
    </div>
  );
}
