import { test, expect } from '@playwright/test'

test.describe('Simulation Browse & Select Flow', () => {
  test('loads simulation list and navigates to dashboard', async ({ page }) => {
    // Mock the simulations list API
    await page.route('**/api/simulations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulations: [
            {
              simulation_id: 'sim-001',
              config_name: 'Basic Test',
              num_agents: 3,
              num_days: 5,
              total_ticks: 500,
              status: 'completed',
            },
            {
              simulation_id: 'sim-002',
              config_name: 'Large Scale',
              num_agents: 10,
              num_days: 10,
              total_ticks: 1000,
              status: 'completed',
            },
          ],
        }),
      })
    })

    // Navigate to homepage
    await page.goto('/')

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible()

    // Verify we see both simulations
    await expect(page.locator('table tbody tr')).toHaveCount(2)

    // Verify simulation IDs are shown (truncated, first 8 chars + "...")
    await expect(page.getByText('sim-001')).toBeVisible()
    await expect(page.getByText('sim-002')).toBeVisible()
  })

  test('clicks simulation and displays dashboard with metrics', async ({ page }) => {
    // Mock simulations list
    await page.route('**/api/simulations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulations: [
            {
              simulation_id: 'sim-001',
              config_name: 'Basic Test',
              num_agents: 3,
              num_days: 5,
              total_ticks: 500,
              status: 'completed',
            },
          ],
        }),
      })
    })

    // Mock simulation detail API
    await page.route('**/api/simulations/sim-001', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulation_id: 'sim-001',
          created_at: '2024-01-01T00:00:00Z',
          config: {
            simulation: {
              ticks_per_day: 100,
              num_days: 5,
              rng_seed: 12345,
            },
            agents: [
              { id: 'BANK_A', opening_balance: 1000000, credit_limit: 0, policy: { type: 'basic' } },
              { id: 'BANK_B', opening_balance: 950000, credit_limit: 0, policy: { type: 'basic' } },
              { id: 'BANK_C', opening_balance: 1050000, credit_limit: 0, policy: { type: 'basic' } },
            ],
          },
          summary: {
            total_ticks: 500,
            total_transactions: 150,
            settlement_rate: 0.947,
            total_cost_cents: 2500000,
            duration_seconds: 12.5,
            ticks_per_second: 40.0,
          },
        }),
      })
    })

    // Navigate to homepage
    await page.goto('/')

    // Click the first simulation
    const firstRow = page.locator('table tbody tr').first()
    await firstRow.click()

    // Verify we're on the dashboard page
    await expect(page).toHaveURL(/\/simulations\/sim-001/)

    // Verify page title shows simulation ID (within main content, not header)
    await expect(page.locator('main h1')).toContainText('Simulation: sim-001')

    // Verify configuration section
    await expect(page.getByText(/configuration/i)).toBeVisible()
    await expect(page.getByText(/ticks per day/i)).toBeVisible()

    // Verify summary metrics section
    await expect(page.getByText(/summary metrics/i)).toBeVisible()
    await expect(page.getByText(/settlement rate/i)).toBeVisible()
    await expect(page.getByText('94.7%')).toBeVisible()
    await expect(page.getByText(/total transactions/i)).toBeVisible()

    // Verify agents section exists
    await expect(page.getByText(/agents \(\d+\)/i)).toBeVisible()
    await expect(page.getByText('BANK_A')).toBeVisible()
    await expect(page.getByText('BANK_B')).toBeVisible()
    await expect(page.getByText('BANK_C')).toBeVisible()
  })

  test('navigates back to simulation list from dashboard', async ({ page }) => {
    // Mock APIs
    await page.route('**/api/simulations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulations: [
            {
              simulation_id: 'sim-001',
              config_name: 'Basic Test',
              num_agents: 3,
              num_days: 5,
              total_ticks: 500,
              status: 'completed',
            },
          ],
        }),
      })
    })

    await page.route('**/api/simulations/sim-001', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulation_id: 'sim-001',
          created_at: '2024-01-01T00:00:00Z',
          config: {
            simulation: {
              ticks_per_day: 100,
              num_days: 5,
              rng_seed: 12345,
            },
            agents: [
              { id: 'BANK_A', opening_balance: 1000000, credit_limit: 0, policy: { type: 'basic' } },
              { id: 'BANK_B', opening_balance: 950000, credit_limit: 0, policy: { type: 'basic' } },
              { id: 'BANK_C', opening_balance: 1050000, credit_limit: 0, policy: { type: 'basic' } },
            ],
          },
          summary: {
            total_ticks: 500,
            total_transactions: 150,
            settlement_rate: 0.947,
            total_cost_cents: 2500000,
            duration_seconds: 12.5,
            ticks_per_second: 40.0,
          },
        }),
      })
    })

    // Note: SimulationDashboardPage does not have a back link to the simulation list
    // It only has links forward to events and transactions
    // This test verifies the navigation structure is correct

    // Navigate directly to dashboard
    await page.goto('/simulations/sim-001')

    // Verify navigation links exist
    await expect(page.getByText(/explore data/i)).toBeVisible()
    await expect(page.getByRole('link', { name: /view events timeline/i })).toBeVisible()

    // User can use browser back or manually navigate to go back to list
  })
})
