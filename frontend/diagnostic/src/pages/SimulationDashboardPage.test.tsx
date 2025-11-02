import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SimulationDashboardPage } from "./SimulationDashboardPage";
import { useSimulation } from "@/hooks/useSimulations";
import { describe, it, expect, vi } from "vitest";

// Mock the useSimulation hook
vi.mock("@/hooks/useSimulations");

const queryClient = new QueryClient();

const mockSimulationData = {
  simulation_id: "sim-123",
  created_at: new Date().toISOString(),
  config: {
    ticks_per_day: 100,
    num_days: 5,
    rng_seed: 12345,
    agents: [],
  },
  summary: {
    settlement_rate: 0.98,
    total_value_settled_cents: 100000,
    total_cost_cents: 500,
    total_transactions: 200,
  },
};

describe("SimulationDashboardPage", () => {
  it("should render simulation details correctly with the new config structure", () => {
    (useSimulation as import("vitest").Mock).mockReturnValue({
      data: mockSimulationData,
      isLoading: false,
      error: null,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/simulations/sim-123"]}>
          <Routes>
            <Route
              path="/simulations/:simId"
              element={<SimulationDashboardPage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Ticks per Day:")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("Number of Days:")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("12345")).toBeInTheDocument();
  });
});
