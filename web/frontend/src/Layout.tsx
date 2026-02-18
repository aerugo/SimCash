import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useGameContext, GameProvider } from './GameContext';
import { useAuthInfo } from './AuthInfoContext';
import { ToastContainer } from './components/Toast';

const NAV_SECTIONS = [
  { to: '/', label: 'Run', icon: '🏠', exact: true },
  { to: '/library/scenarios', label: 'Library', icon: '📚', match: '/library' },
  { to: '/create', label: 'Create', icon: '✏️' },
  { to: '/docs', label: 'Docs', icon: '📖', match: '/docs' },
];

function LayoutInner() {
  const { simId, state, gameId } = useGameContext();
  const { isAdmin, userEmail, onSignOut } = useAuthInfo();
  const location = useLocation();

  const showExperiment = !!gameId;
  const showSimulation = !!simId;

  const isActive = (section: typeof NAV_SECTIONS[0]) => {
    if (section.exact) return location.pathname === section.to;
    const matchPath = section.match || section.to;
    return location.pathname.startsWith(matchPath);
  };

  const isLibrary = location.pathname.startsWith('/library');
  const isScenarios = location.pathname.startsWith('/library/scenarios');
  const isPolicies = location.pathname.startsWith('/library/policies');
  const isSimulation = location.pathname.startsWith('/simulation');

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-700 bg-[#0f172a]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <NavLink to="/" className="text-2xl font-bold bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
              SimCash
            </NavLink>
            <span className="text-xs text-slate-500 hidden sm:inline">Interactive Payment Simulator</span>
          </div>
          <div className="flex items-center gap-3">
            {simId && state && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <span className="font-mono bg-slate-800 px-2 py-1 rounded text-xs">{simId}</span>
                <span className="text-xs">
                  Tick {state.current_tick}/{state.total_ticks}
                  {state.is_complete && <span className="ml-1 text-green-400">✓</span>}
                </span>
              </div>
            )}
            {isAdmin && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `text-xs font-medium transition-colors ${isActive ? 'text-amber-300' : 'text-amber-400 hover:text-amber-300'}`
                }
              >
                👑 Admin
              </NavLink>
            )}
            <span className="text-xs text-slate-500 hidden md:inline">{userEmail}</span>
            <button onClick={onSignOut} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Sign out</button>
          </div>
        </div>

        {/* Section bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex gap-1 overflow-x-auto pb-0 -mb-px">
            {NAV_SECTIONS.map(section => (
              <NavLink
                key={section.to}
                to={section.to}
                end={section.exact}
                className={() =>
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                    isActive(section)
                      ? 'border-sky-400 text-sky-400'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`
                }
              >
                <span className="sm:mr-1 text-base sm:text-sm">{section.icon}</span>
                <span className="hidden sm:inline">{section.label}</span>
              </NavLink>
            ))}
            {showExperiment && (
              <NavLink
                to={`/experiment/${gameId}`}
                className={({ isActive: active }) =>
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                    active || location.pathname.startsWith('/experiment')
                      ? 'border-sky-400 text-sky-400'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`
                }
              >
                <span className="mr-1">🧪</span>
                <span className="hidden sm:inline">Experiment</span>
              </NavLink>
            )}
            {showSimulation && (
              <NavLink
                to="/simulation/dashboard"
                className={() =>
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                    isSimulation
                      ? 'border-sky-400 text-sky-400'
                      : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`
                }
              >
                <span className="mr-1">📊</span>
                <span className="hidden sm:inline">Simulation</span>
              </NavLink>
            )}
          </div>
        </div>
      </header>

      {/* Library sub-tab bar */}
      {isLibrary && (
        <div className="border-b border-slate-700/50 bg-[#0f172a]/60 sticky top-[57px] z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex gap-1 overflow-x-auto py-0 -mb-px">
              <NavLink
                to="/library/scenarios"
                className={() =>
                  `px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                    isScenarios ? 'border-violet-400 text-violet-300' : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`
                }
              >
                Scenarios
              </NavLink>
              <NavLink
                to="/library/policies"
                className={() =>
                  `px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                    isPolicies ? 'border-violet-400 text-violet-300' : 'border-transparent text-slate-500 hover:text-slate-300'
                  }`
                }
              >
                Policies
              </NavLink>
            </div>
          </div>
        </div>
      )}

      {/* Simulation sub-tab bar */}
      {isSimulation && (
        <div className="border-b border-slate-700/50 bg-[#0f172a]/60 sticky top-[57px] z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex gap-1 overflow-x-auto py-0 -mb-px">
              {[
                { to: '/simulation/dashboard', label: 'Dashboard' },
                { to: '/simulation/agents', label: 'Agents' },
                { to: '/simulation/events', label: 'Events' },
                { to: '/simulation/config', label: 'Config' },
                { to: '/simulation/replay', label: 'Replay' },
                { to: '/simulation/analysis', label: 'Analysis' },
              ].map(tab => (
                <NavLink
                  key={tab.to}
                  to={tab.to}
                  className={({ isActive: active }) =>
                    `px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                      active ? 'border-violet-400 text-violet-300' : 'border-transparent text-slate-500 hover:text-slate-300'
                    }`
                  }
                >
                  {tab.label}
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>

      {/* Keyboard hint */}
      {simId && isSimulation && (
        <div className="fixed bottom-4 left-4 text-[10px] text-slate-600 hidden lg:block pointer-events-none">
          Space: play/pause · →: step · R: reset
        </div>
      )}

      <ToastContainer />
    </div>
  );
}

export function Layout() {
  const authInfo = useAuthInfo();
  return (
    <GameProvider isAdmin={authInfo.isAdmin} userEmail={authInfo.userEmail} onSignOut={authInfo.onSignOut}>
      <LayoutInner />
    </GameProvider>
  );
}
