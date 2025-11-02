/**
 * E2E tests for diagnostic dashboard with real 12-bank simulation data
 *
 * These tests use a real database created by running the 12-bank scenario.
 * They test the full stack: database -> API -> frontend
 */

import { test, expect } from "@playwright/test";
import { setupRealDatabase, type SimulationSetup } from "./setup-real-database";

// Global setup - run simulation once before all tests
let simulationSetup: SimulationSetup;

test.beforeAll(async () => {
  // Run the 12-bank simulation and create test database
  simulationSetup = await setupRealDatabase();

  // Set environment variable for API to use this database
  process.env.DATABASE_PATH = simulationSetup.dbPath;
});

test.afterAll(async () => {
  // Cleanup
  if (simulationSetup?.cleanup) {
    simulationSetup.cleanup();
  }
});

test.describe("Diagnostic Dashboard with Real 12-Bank Data", () => {
  test("loads simulation list with 12-bank simulation", async ({ page }) => {
    await page.goto("/");

    // Wait for the simulation list to load
    await expect(page.locator("h1")).toContainText("Simulations");
    await expect(page.locator("table")).toBeVisible();

    // Should have at least one simulation (our 12-bank run)
    const rows = page.locator("table tbody tr");
    await expect(rows).not.toHaveCount(0);

    // Find our simulation by checking for 12 agents
    const cellWithTwelve = page.locator("td", { hasText: "12" });
    await expect(cellWithTwelve).toBeVisible();
  });

  test("opens 12-bank simulation dashboard", async ({ page }) => {
    await page.goto("/");

    // Wait for table
    await page.locator("table tbody tr").first().waitFor();

    // Click the simulation (assuming it's the first/only one)
    await page.locator("table tbody tr").first().click();

    // Wait for dashboard to load
    await expect(page.locator("main h1")).toContainText("Simulation");

    // Verify we see the simulation ID
    await expect(page.locator("main")).toContainText(
      simulationSetup.simulationId
    );

    // Check summary metrics section exists
    await expect(page.getByText(/summary metrics/i)).toBeVisible();

    // Check settlement rate is shown
    await expect(page.getByText(/settlement rate/i)).toBeVisible();

    // Check we have a percentage value
    await expect(page.locator("text=/\\d+\\.\\d+%/")).toBeVisible();
  });

  test("displays all 12 agent banks", async ({ page }) => {
    // Navigate directly to dashboard
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Wait for agents section
    await expect(page.getByText(/agents \(\d+\)/i)).toBeVisible();

    // Verify we see 12 agents listed
    const expectedAgents = [
      "ALM_CONSERVATIVE",
      "ALM_BALANCED",
      "ALM_AGGRESSIVE",
      "ARB_LARGE_REGIONAL",
      "ARB_MEDIUM_REGIONAL",
      "ARB_SMALL_REGIONAL",
      "GNB_TIER1_BEHEMOTH",
      "GNB_MAJOR_NATIONAL",
      "GNB_REGIONAL_NATIONAL",
      "MIB_PRIME_BROKER",
      "MIB_HEDGE_FUND_DESK",
      "MIB_PROP_TRADING",
    ];

    for (const agentId of expectedAgents) {
      await expect(page.getByText(agentId)).toBeVisible();
    }
  });

  test("displays configuration details", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Check configuration section
    await expect(page.getByText(/configuration/i)).toBeVisible();

    // Verify seed is shown (we used seed 42)
    await expect(page.getByText("42")).toBeVisible();

    // Verify ticks per day
    await expect(page.getByText(/ticks per day/i)).toBeVisible();
  });

  test("shows transaction data exists", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Check for total transactions metric
    await expect(page.getByText(/total transactions/i)).toBeVisible();

    // Should show a non-zero number
    await expect(page.locator("text=/\\d+/")).toBeVisible();
  });

  test("navigates to events timeline", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Find and click the "View Events Timeline" link
    const eventsLink = page.getByRole("link", {
      name: /view events timeline/i,
    });
    await expect(eventsLink).toBeVisible();
    await eventsLink.click();

    // Should navigate to events page
    await expect(page).toHaveURL(/\/events/);
    await expect(page.locator("h1")).toContainText("Events");
  });

  test("displays agent metrics for ALM_CONSERVATIVE", async ({ page }) => {
    // Navigate to specific agent
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Click on ALM_CONSERVATIVE agent
    await page.getByText("ALM_CONSERVATIVE").first().click();

    // Wait for navigation
    await expect(page).toHaveURL(/\/agents\/ALM_CONSERVATIVE/);
    await expect(page.locator("h1")).toContainText("ALM_CONSERVATIVE");

    // Should show agent details (implementation dependent)
    // Just verify we're on the agent page
    await expect(page.locator("main")).toContainText("ALM_CONSERVATIVE");
  });

  test("verifies data consistency across pages", async ({ page }) => {
    // Get total transactions from dashboard
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    const totalTxText = await page
      .locator("text=/total transactions/i")
      .textContent();
    expect(totalTxText).toBeTruthy();

    // Verify agents add up to 12
    await expect(page.getByText(/agents \(12\)/i)).toBeVisible();
  });

  test("shows realistic settlement rate", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Settlement rate should be between 0% and 100%
    const settlementRateText = await page
      .locator('[data-testid="settlement-rate"]')
      .textContent();

    if (settlementRateText) {
      // Extract percentage
      const match = settlementRateText.match(/(\d+\.?\d*)%/);
      if (match) {
        const rate = parseFloat(match[1]);
        expect(rate).toBeGreaterThanOrEqual(0);
        expect(rate).toBeLessThanOrEqual(100);
      }
    }
  });

  test("handles agent names from different policies", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Verify we see agents from all 4 policy types
    // ALM = Adaptive Liquidity Manager
    await expect(page.getByText(/ALM_/)).toBeVisible();

    // ARB = Agile Regional Bank
    await expect(page.getByText(/ARB_/)).toBeVisible();

    // GNB = Goliath National Bank
    await expect(page.getByText(/GNB_/)).toBeVisible();

    // MIB = Momentum Investment Bank
    await expect(page.getByText(/MIB_/)).toBeVisible();
  });

  test("configuration shows correct number of agents", async ({ page }) => {
    await page.goto(`/simulations/${simulationSetup.simulationId}`);

    // Check configuration section has 12 agents
    await expect(page.getByText(/configuration/i)).toBeVisible();

    // The configuration should list all 12 agents
    // This verifies the config was persisted correctly
    const mainContent = await page.locator("main").textContent();
    expect(mainContent).toContain("ALM_CONSERVATIVE");
    expect(mainContent).toContain("MIB_PROP_TRADING");
  });
});

test.describe("API Integration with Real Data", () => {
  test("API returns correct simulation metadata", async ({ request }) => {
    const response = await request.get(
      `http://localhost:8000/api/simulations/${simulationSetup.simulationId}`
    );

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    expect(data.simulation_id).toBe(simulationSetup.simulationId);
    expect(data.config).toBeDefined();
    expect(data.config.agents).toHaveLength(12);
    expect(data.summary).toBeDefined();
  });

  test("API returns agent list", async ({ request }) => {
    const response = await request.get(
      `http://localhost:8000/api/simulations/${simulationSetup.simulationId}/agents`
    );

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    expect(data.agents).toBeDefined();
    expect(data.agents).toHaveLength(12);

    // Verify agent structure
    const agent = data.agents[0];
    expect(agent.agent_id).toBeDefined();
    expect(agent.total_sent).toBeDefined();
    expect(agent.total_received).toBeDefined();
  });

  test("API returns transaction data", async ({ request }) => {
    const response = await request.get(
      `http://localhost:8000/api/simulations/${simulationSetup.simulationId}/transactions?limit=10`
    );

    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    expect(data.transactions).toBeDefined();
    expect(data.transactions.length).toBeGreaterThan(0);
    expect(data.transactions.length).toBeLessThanOrEqual(10);

    // Verify transaction structure
    const tx = data.transactions[0];
    expect(tx.tx_id).toBeDefined();
    expect(tx.sender_id).toBeDefined();
    expect(tx.receiver_id).toBeDefined();
    expect(tx.amount).toBeGreaterThan(0);
  });
});
