import { useNavigate } from 'react-router-dom'
import { useSimulations } from '../hooks/useSimulations'
import { Button } from '../components/ui/button'
import type { Simulation } from '../types/api'

export function SimulationListPage() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useSimulations()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-600">Loading simulations...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-600">Error loading simulations: {(error as Error).message}</p>
      </div>
    )
  }

  const simulations = data?.simulations || []

  if (simulations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <p className="text-gray-600">No simulations found</p>
        <p className="text-sm text-gray-500">
          Run a simulation to see it appear here
        </p>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Simulations</h1>
        <p className="text-gray-600">
          Browse and explore saved simulation runs
        </p>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Simulation ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Agents
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Days
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Started
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {simulations.map((sim) => (
              <SimulationRow
                key={sim.simulation_id}
                simulation={sim}
                onClick={() => navigate(`/simulations/${sim.simulation_id}`)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

interface SimulationRowProps {
  simulation: Simulation
  onClick: () => void
}

function SimulationRow({ simulation, onClick }: SimulationRowProps) {
  const isActive = simulation.current_tick !== undefined
  const status = simulation.status || (isActive ? 'running' : 'unknown')

  return (
    <tr
      className="hover:bg-gray-50 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm font-medium text-gray-900">
          {simulation.simulation_id.substring(0, 8)}...
        </div>
        {simulation.config_file && (
          <div className="text-xs text-gray-500">{simulation.config_file}</div>
        )}
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <StatusBadge status={status} />
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
        {simulation.num_agents || '-'}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
        {simulation.num_days || '-'}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        {simulation.started_at
          ? new Date(simulation.started_at).toLocaleString()
          : isActive
          ? 'Active'
          : '-'}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-sm">
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation()
            onClick()
          }}
        >
          View
        </Button>
      </td>
    </tr>
  )
}

interface StatusBadgeProps {
  status: string
}

function StatusBadge({ status }: StatusBadgeProps) {
  const colors: Record<string, string> = {
    completed: 'bg-green-100 text-green-800',
    running: 'bg-blue-100 text-blue-800',
    pending: 'bg-yellow-100 text-yellow-800',
    failed: 'bg-red-100 text-red-800',
  }

  const colorClass = colors[status] || 'bg-gray-100 text-gray-800'

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}
    >
      {status}
    </span>
  )
}
