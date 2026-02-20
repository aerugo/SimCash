import { createBrowserRouter, Navigate, useNavigate } from 'react-router-dom';
import { Layout } from './Layout';
import { HomeView } from './views/HomeView';
import { GameView } from './views/GameView';
import { ScenarioLibraryView } from './views/ScenarioLibraryView';
import { PolicyLibraryView } from './views/PolicyLibraryView';
import { CreateView } from './views/CreateView';
import { DocsView } from './views/DocsView';
import { AdminDashboard } from './components/AdminDashboard';
import { DashboardView } from './views/DashboardView';
import { EventsView } from './views/EventsView';
import { AgentsView } from './views/AgentsView';
import ExperimentsView from './views/ExperimentsView';
import { ConfigView } from './views/ConfigView';
import { ReplayView } from './views/ReplayView';
import { AnalysisView } from './views/AnalysisView';
import { LibraryView } from './views/LibraryView';
import { useGameContext } from './GameContext';
import { useAuthInfo } from './AuthInfoContext';
import { LoginPrompt } from './components/LoginPrompt';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isGuest } = useAuthInfo();
  if (isGuest) {
    return <LoginPrompt reason="You need to sign in to access this feature." />;
  }
  return <>{children}</>;
}

function AdminRoute() {
  const navigate = useNavigate();
  return <AdminDashboard onClose={() => navigate(-1)} />;
}

function SimDashboardRoute() {
  const { state, events, isRunning, speed, handleTick, handleRun, handlePause, handleReset, setSpeed, reasoning } = useGameContext();
  const navigate = useNavigate();
  if (!state) return <Navigate to="/" replace />;
  return <DashboardView state={state} events={events} isRunning={isRunning} speed={speed} onTick={handleTick} onRun={handleRun} onPause={handlePause} onReset={handleReset} onSpeedChange={setSpeed} reasoning={reasoning} onNavigateToAgents={() => navigate('/simulation/agents')} />;
}

function SimEventsRoute() {
  const { events } = useGameContext();
  return <EventsView events={events} />;
}

function SimAgentsRoute() {
  const { reasoning } = useGameContext();
  return <AgentsView reasoning={reasoning} />;
}

function SimConfigRoute() {
  const { simId } = useGameContext();
  if (!simId) return <Navigate to="/" replace />;
  return <ConfigView simId={simId} />;
}

function SimReplayRoute() {
  const { simId, state } = useGameContext();
  if (!simId || !state) return <Navigate to="/" replace />;
  return <ReplayView simId={simId} state={state} />;
}

function SimAnalysisRoute() {
  const { simId, state, events } = useGameContext();
  if (!simId || !state) return <Navigate to="/" replace />;
  return <AnalysisView state={state} events={events} simId={simId} />;
}

function SimLibraryRoute() {
  const { handleLaunch } = useGameContext();
  return <LibraryView onLaunch={handleLaunch} />;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomeView /> },
      { path: 'library', element: <Navigate to="scenarios" replace /> },
      { path: 'library/scenarios', element: <ScenarioLibraryView /> },
      { path: 'library/scenarios/:scenarioId', element: <ScenarioLibraryView /> },
      { path: 'library/policies', element: <PolicyLibraryView /> },
      { path: 'library/policies/:policyId', element: <PolicyLibraryView /> },
      { path: 'create', element: <RequireAuth><CreateView /></RequireAuth> },
      { path: 'experiments', element: <RequireAuth><ExperimentsView /></RequireAuth> },
      { path: 'experiment/:gameId', element: <GameView /> },
      { path: 'docs', element: <DocsView /> },
      { path: 'docs/*', element: <DocsView /> },
      { path: 'admin', element: <RequireAuth><AdminRoute /></RequireAuth> },
      // Legacy simulation routes
      { path: 'simulation/dashboard', element: <SimDashboardRoute /> },
      { path: 'simulation/agents', element: <SimAgentsRoute /> },
      { path: 'simulation/events', element: <SimEventsRoute /> },
      { path: 'simulation/config', element: <SimConfigRoute /> },
      { path: 'simulation/replay', element: <SimReplayRoute /> },
      { path: 'simulation/analysis', element: <SimAnalysisRoute /> },
      { path: 'simulation/library', element: <SimLibraryRoute /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
