import { useParams, Link } from "react-router-dom";
import { useSimulation } from "@/hooks/useSimulations";
import { formatCurrency } from "@/utils/currency";

export function SimulationDashboardPage() {
  const { simId } = useParams<{ simId: string }>();
  const { data, isLoading, error } = useSimulation(simId!);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg text-gray-600">Loading simulation data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          <h2 className="font-bold mb-2">Error loading simulation</h2>
          <p>
            {error instanceof Error ? error.message : "Unknown error occurred"}
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { simulation_id, created_at, config, summary } = data;
  const settlementRatePercent = (summary.settlement_rate * 100).toFixed(1);

  // Handle both nested (config.simulation.{field}) and flat (config.{field}) structures
  const simConfig = config.simulation || config;
  const agents = config.agents || [];

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">
          Simulation Dashboard
        </h2>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Simulation: {simulation_id}
        </h1>
        <p className="text-gray-600">
          Created: {new Date(created_at).toLocaleString()}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Configuration
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-600">Ticks per Day:</dt>
              <dd className="font-medium text-gray-900">
                {simConfig.ticks_per_day}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Number of Days:</dt>
              <dd className="font-medium text-gray-900">
                {simConfig.num_days}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">RNG Seed:</dt>
              <dd className="font-medium font-mono text-sm text-gray-900">
                {simConfig.rng_seed}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Number of Agents:</dt>
              <dd className="font-medium text-gray-900">{agents.length}</dd>
            </div>
          </dl>
        </section>

        {/* Summary Metrics Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Summary Metrics
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Ticks:</dt>
              <dd className="font-medium text-gray-900">
                {summary.total_ticks}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Transactions:</dt>
              <dd className="font-medium text-gray-900">
                {summary.total_transactions}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Settlement Rate:</dt>
              <dd className="font-medium text-lg text-blue-600">
                {settlementRatePercent}%
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Cost:</dt>
              <dd className="font-medium text-gray-900">
                {formatCurrency(summary.total_cost_cents)}
              </dd>
            </div>
            {summary.duration_seconds && (
              <div className="flex justify-between">
                <dt className="text-gray-600">Duration:</dt>
                <dd className="font-medium text-gray-900">
                  {summary.duration_seconds.toFixed(2)}s
                </dd>
              </div>
            )}
            {summary.ticks_per_second && (
              <div className="flex justify-between">
                <dt className="text-gray-600">Performance:</dt>
                <dd className="font-medium text-gray-900">
                  {summary.ticks_per_second.toFixed(0)} ticks/s
                </dd>
              </div>
            )}
          </dl>
        </section>

        {/* Agents Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Agents ({agents.length})
          </h2>
          <ul className="space-y-2">
            {agents.map((agent) => (
              <li
                key={agent.id}
                className="flex justify-between items-center p-3 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
              >
                <div>
                  <Link
                    to={`/simulations/${simulation_id}/agents/${agent.id}`}
                    className="font-medium text-gray-900 hover:text-blue-600 underline"
                  >
                    {agent.id}
                  </Link>
                  <div className="text-sm text-gray-600">
                    Balance: {formatCurrency(agent.opening_balance)} | Credit:{" "}
                    {formatCurrency(agent.credit_limit)}
                  </div>
                </div>
                <Link
                  to={`/simulations/${simulation_id}/agents/${agent.id}`}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  View Details →
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {/* Navigation Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Explore Data
          </h2>
          <div className="space-y-3">
            <Link
              to={`/simulations/${simulation_id}/events`}
              className="block w-full px-4 py-3 bg-blue-600 text-white text-center rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              View Events Timeline
            </Link>
            <Link
              to={`/simulations/${simulation_id}/events`}
              className="block w-full px-4 py-3 bg-green-600 text-white text-center rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              View Transactions
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
