import { Routes, Route } from 'react-router-dom'
import { SimulationListPage } from './pages/SimulationListPage'
import { SimulationDashboardPage } from './pages/SimulationDashboardPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { EventTimelinePage } from './pages/EventTimelinePage'
import { TransactionDetailPage } from './pages/TransactionDetailPage'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900">
            Payment Simulator - Diagnostic Client
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<SimulationListPage />} />
          <Route path="/simulations/:simId" element={<SimulationDashboardPage />} />
          <Route path="/simulations/:simId/agents/:agentId" element={<AgentDetailPage />} />
          <Route path="/simulations/:simId/events" element={<EventTimelinePage />} />
          <Route path="/simulations/:simId/transactions/:txId" element={<TransactionDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
