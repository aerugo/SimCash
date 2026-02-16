import { useState, useCallback, useRef, useEffect } from 'react';
import type { SimulationState, TickResult, SimEvent, Preset } from './types';
import { createSimulation, getPresets, connectWebSocket } from './api';
import { BalanceChart } from './components/BalanceChart';
import { CostChart } from './components/CostChart';
import { EventLog } from './components/EventLog';
import { AgentCards } from './components/AgentCards';
import { Controls } from './components/Controls';

function App() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [simId, setSimId] = useState<string | null>(null);
  const [state, setState] = useState<SimulationState | null>(null);
  const [events, setEvents] = useState<SimEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(500);
  const [selectedPreset, setSelectedPreset] = useState('exp3');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    getPresets().then(setPresets);
  }, []);

  const handleCreate = useCallback(async () => {
    const res = await createSimulation(selectedPreset);
    setSimId(res.sim_id);
    setEvents([]);
    setIsRunning(false);

    // Connect WebSocket
    const ws = connectWebSocket(res.sim_id);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'state' || msg.type === 'paused' || msg.type === 'complete') {
        setState(msg.data);
        if (msg.type === 'complete') setIsRunning(false);
      } else if (msg.type === 'tick') {
        const tick = msg.data as TickResult;
        setState(prev => prev ? {
          ...prev,
          current_tick: tick.tick + 1,
          is_complete: tick.is_complete,
          agents: tick.agents,
          balance_history: tick.balance_history,
          cost_history: tick.cost_history,
        } : prev);
        setEvents(prev => [...prev, ...tick.events]);
        if (tick.is_complete) setIsRunning(false);
      }
    };

    ws.onclose = () => {
      setIsRunning(false);
    };
  }, [selectedPreset]);

  const handleTick = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'tick' }));
  }, []);

  const handleRun = useCallback(() => {
    setIsRunning(true);
    wsRef.current?.send(JSON.stringify({ action: 'run', speed_ms: speed }));
  }, [speed]);

  const handlePause = useCallback(() => {
    setIsRunning(false);
    wsRef.current?.send(JSON.stringify({ action: 'pause' }));
  }, []);

  const handleReset = useCallback(() => {
    wsRef.current?.close();
    setSimId(null);
    setState(null);
    setEvents([]);
    setIsRunning(false);
  }, []);

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-700 bg-[#0f172a]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-2xl font-bold bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
              SimCash
            </div>
            <span className="text-sm text-slate-500">Interactive Payment Simulator</span>
          </div>
          {simId && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <span className="font-mono bg-slate-800 px-2 py-1 rounded">{simId}</span>
              {state && (
                <span>
                  Tick {state.current_tick}/{state.total_ticks}
                  {state.is_complete && <span className="ml-2 text-green-400">✓ Complete</span>}
                </span>
              )}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {!simId ? (
          /* Scenario Selection */
          <div className="max-w-2xl mx-auto mt-20">
            <h2 className="text-3xl font-bold mb-2 text-center">Payment System Simulator</h2>
            <p className="text-slate-400 text-center mb-10">
              Watch AI agents make real-time decisions about liquidity allocation and payment timing
            </p>

            <div className="space-y-3 mb-8">
              {presets.map(p => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPreset(p.id)}
                  className={`w-full text-left p-4 rounded-xl border transition-all ${
                    selectedPreset === p.id
                      ? 'border-sky-500 bg-sky-500/10'
                      : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-sm text-slate-400 mt-1">{p.description}</div>
                    </div>
                    <div className="text-xs text-slate-500 flex gap-3">
                      <span>{p.ticks_per_day} ticks</span>
                      <span>{p.num_agents} banks</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <button
              onClick={handleCreate}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 font-semibold text-white hover:from-sky-400 hover:to-violet-400 transition-all shadow-lg shadow-sky-500/20"
            >
              Launch Simulation
            </button>
          </div>
        ) : (
          /* Simulation Dashboard */
          <div className="space-y-6">
            {/* Controls */}
            <Controls
              isRunning={isRunning}
              isComplete={state?.is_complete ?? false}
              speed={speed}
              onTick={handleTick}
              onRun={handleRun}
              onPause={handlePause}
              onReset={handleReset}
              onSpeedChange={setSpeed}
            />

            {/* Agent Cards */}
            {state && <AgentCards agents={state.agents} />}

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {state && state.balance_history && Object.keys(state.balance_history).length > 0 && (
                <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4">Bank Balances</h3>
                  <BalanceChart history={state.balance_history} />
                </div>
              )}

              {state && state.cost_history && Object.keys(state.cost_history).length > 0 && (
                <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4">Accumulated Costs</h3>
                  <CostChart history={state.cost_history} />
                </div>
              )}
            </div>

            {/* Event Log */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">
                Event Log ({events.length} events)
              </h3>
              <EventLog events={events} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
