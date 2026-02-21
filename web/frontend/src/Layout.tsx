import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useGameContext, GameProvider } from './GameContext';
import { useAuthInfo } from './AuthInfoContext';
import { ToastContainer } from './components/Toast';
import { useTheme } from './hooks/useTheme';
import { ChangePasswordModal } from './components/ChangePasswordModal';

const NAV_SECTIONS = [
  { to: '/', label: 'Run', icon: '🏠', exact: true },
  { to: '/experiments', label: 'History', icon: '📋' },
  { to: '/library/scenarios', label: 'Library', icon: '📚', match: '/library' },
  { to: '/create', label: 'Create', icon: '✏️' },
  { to: '/docs', label: 'Docs', icon: '📖', match: '/docs' },
];

function LayoutInner() {
  const { simId, state, gameId } = useGameContext();
  const { isAdmin, userEmail, isGuest, onSignOut, onSignIn } = useAuthInfo();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const location = useLocation();
  useTheme(); // apply theme on mount

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
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}>
      {/* Header */}
      <header className="backdrop-blur-sm sticky top-0 z-50" style={{ borderBottom: '1px solid var(--border-color)', backgroundColor: 'color-mix(in srgb, var(--bg-base) 80%, transparent)' }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <NavLink to="/" className="text-2xl font-bold" style={{ color: 'var(--text-accent)' }}>
              SimCash
            </NavLink>
            <span className="text-xs hidden sm:inline" style={{ color: 'var(--text-muted)' }}>Interactive Payment Simulator</span>
          </div>
          <div className="flex items-center gap-3">
            {simId && state && (
              <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <span className="font-mono px-2 py-1 rounded text-xs" style={{ backgroundColor: 'var(--bg-surface)' }}>{simId}</span>
                <span className="text-xs">
                  Tick {state.current_tick}/{state.total_ticks}
                  {state.is_complete && <span className="ml-1" style={{ color: 'var(--color-success)' }}>✓</span>}
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
            {/* Theme toggle hidden — light mode is default */}
            {isGuest ? (
              <button onClick={onSignIn} className="px-3 py-1.5 text-xs font-medium rounded-lg transition-colors" style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-accent)', border: '1px solid var(--border-color)' }}>Sign In</button>
            ) : (
              <>
                <span className="text-xs hidden md:inline" style={{ color: 'var(--text-muted)' }}>{userEmail}</span>
                <button onClick={() => setShowChangePassword(true)} className="text-xs transition-colors hidden md:inline" style={{ color: 'var(--text-muted)' }}>🔒</button>
                <button onClick={onSignOut} className="text-xs transition-colors" style={{ color: 'var(--text-muted)' }}>Sign out</button>
              </>
            )}
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
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors`
                }
                style={{ borderColor: isActive(section) ? 'var(--text-accent)' : 'transparent', color: isActive(section) ? 'var(--text-accent)' : 'var(--text-muted)' }}
              >
                <span className="sm:mr-1 text-base sm:text-sm">{section.icon}</span>
                <span className="hidden sm:inline">{section.label}</span>
              </NavLink>
            ))}
            {showExperiment && (
              <NavLink
                to={`/experiment/${gameId}`}
                className={() =>
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors`
                }
                style={{ borderColor: location.pathname.startsWith('/experiment') ? 'var(--text-accent)' : 'transparent', color: location.pathname.startsWith('/experiment') ? 'var(--text-accent)' : 'var(--text-muted)' }}
              >
                <span className="mr-1">🧪</span>
                <span className="hidden sm:inline">Experiment</span>
              </NavLink>
            )}
            {showSimulation && (
              <NavLink
                to="/simulation/dashboard"
                className={() =>
                  `px-3 py-2 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors`
                }
                style={{ borderColor: isSimulation ? 'var(--text-accent)' : 'transparent', color: isSimulation ? 'var(--text-accent)' : 'var(--text-muted)' }}
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
        <div className="sticky top-[57px] z-40" style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'color-mix(in srgb, var(--bg-base) 60%, transparent)' }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex gap-1 overflow-x-auto py-0 -mb-px">
              <NavLink to="/library/scenarios" className="px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors" style={{ borderColor: isScenarios ? 'var(--text-accent-2)' : 'transparent', color: isScenarios ? 'var(--text-accent-2)' : 'var(--text-muted)' }}>Scenarios</NavLink>
              <NavLink to="/library/policies" className="px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors" style={{ borderColor: isPolicies ? 'var(--text-accent-2)' : 'transparent', color: isPolicies ? 'var(--text-accent-2)' : 'var(--text-muted)' }}>Policies</NavLink>
            </div>
          </div>
        </div>
      )}

      {/* Simulation sub-tab bar */}
      {isSimulation && (
        <div className="sticky top-[57px] z-40" style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'color-mix(in srgb, var(--bg-base) 60%, transparent)' }}>
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
                  className="px-3 py-1.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors"
                  style={({ isActive: active }) => ({ borderColor: active ? 'var(--text-accent-2)' : 'transparent', color: active ? 'var(--text-accent-2)' : 'var(--text-muted)' })}
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
        <div className="fixed bottom-4 left-4 text-[10px] hidden lg:block pointer-events-none" style={{ color: 'var(--text-muted)' }}>
          Space: play/pause · →: step · R: reset
        </div>
      )}

      <ToastContainer />
      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
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
