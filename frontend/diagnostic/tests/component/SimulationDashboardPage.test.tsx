import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { SimulationDashboardPage } from "@/pages/SimulationDashboardPage";
import * as simulationsApi from "@/api/simulations";

// Helper to wrap component with providers and route params
function renderWithProviders(
  ui: React.ReactElement,
  { simId = "sim-001" } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/simulations/${simId}`]}>
        <Routes>
          <Route path="/simulations/:simId" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SimulationDashboardPage", () => {
  it("renders loading state initially", () => {
    vi.spyOn(simulationsApi, "fetchSimulationMetadata").mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithProviders(<SimulationDashboardPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders error state when fetch fails", async () => {
    vi.spyOn(simulationsApi, "fetchSimulationMetadata").mockRejectedValue(
      new Error("Simulation not found")
    );

    renderWithProviders(<SimulationDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/simulation not found/i)).toBeInTheDocument();
  });

  it("renders simulation metadata and config", async () => {
    vi.spyOn(simulationsApi, "fetchSimulationMetadata").mockResolvedValue({
      simulation_id: "sim-001",
      created_at: "2025-11-02T10:00:00Z",
      config: {
        ticks_per_day: 100,
        num_days: 5,
        rng_seed: 12345,
        agents: [
          {
            id: "BANK_A",
            opening_balance: 1000000,
            credit_limit: 500000,
            policy: { type: "Fifo" },
          },
          {
            id: "BANK_B",
            opening_balance: 2000000,
            credit_limit: 0,
            policy: { type: "Fifo" },
          },
        ],
      },
      summary: {
        total_ticks: 500,
        total_transactions: 150,
        settlement_rate: 0.947,
        total_cost_cents: 2500000,
        duration_seconds: 12.5,
        ticks_per_second: 40,
      },
    });

    renderWithProviders(<SimulationDashboardPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });

    // Should show simulation ID
    expect(screen.getByText(/sim-001/)).toBeInTheDocument();

    // Should show config details
    expect(screen.getByText("100")).toBeInTheDocument(); // ticks_per_day
    expect(screen.getByText("5")).toBeInTheDocument(); // num_days
    expect(screen.getByText("2")).toBeInTheDocument(); // num agents

    // Should show summary metrics
    expect(screen.getByText("500")).toBeInTheDocument(); // total_ticks
    expect(screen.getByText("150")).toBeInTheDocument(); // total_transactions
    expect(screen.getByText(/94\.7%/)).toBeInTheDocument(); // settlement_rate
  });

  it("shows agent list with links", async () => {
    vi.spyOn(simulationsApi, "fetchSimulationMetadata").mockResolvedValue({
      simulation_id: "sim-001",
      created_at: "2025-11-02T10:00:00Z",
      config: {
        ticks_per_day: 100,
        num_days: 5,
        rng_seed: 12345,
        agents: [
          {
            id: "BANK_A",
            opening_balance: 1000000,
            credit_limit: 500000,
            policy: { type: "Fifo" },
          },
          {
            id: "BANK_B",
            opening_balance: 2000000,
            credit_limit: 0,
            policy: { type: "Fifo" },
          },
        ],
      },
      summary: {
        total_ticks: 500,
        total_transactions: 150,
        settlement_rate: 0.947,
        total_cost_cents: 2500000,
        duration_seconds: 12.5,
        ticks_per_second: 40,
      },
    });

    renderWithProviders(<SimulationDashboardPage />);

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });

    // Should show agent IDs
    expect(screen.getByText("BANK_A")).toBeInTheDocument();
    expect(screen.getByText("BANK_B")).toBeInTheDocument();
  });

  it("shows navigation links to related pages", async () => {
    vi.spyOn(simulationsApi, "fetchSimulationMetadata").mockResolvedValue({
      simulation_id: "sim-001",
      created_at: "2025-11-02T10:00:00Z",
      config: {
        ticks_per_day: 100,
        num_days: 5,
        rng_seed: 12345,
        agents: [
          {
            id: "BANK_A",
            opening_balance: 1000000,
            credit_limit: 500000,
            policy: { type: "Fifo" },
          },
        ],
      },
      summary: {
        total_ticks: 500,
        total_transactions: 150,
        settlement_rate: 0.947,
        total_cost_cents: 2500000,
        duration_seconds: 12.5,
        ticks_per_second: 40,
      },
    });

    renderWithProviders(<SimulationDashboardPage />);

    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });

    // Should have link to events
    expect(
      screen.getByRole("link", { name: /view events/i })
    ).toBeInTheDocument();
  });
});
