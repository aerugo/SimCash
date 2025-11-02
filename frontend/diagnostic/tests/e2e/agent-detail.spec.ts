import { test, expect } from '@playwright/test'

test.describe('Agent Inspection Flow', () => {
  test('navigates from dashboard to agent detail page', async ({ page }) => {
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

    // Mock agent timeline API
    await page.route('**/api/simulations/sim-001/agents/BANK_A/timeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_id: 'BANK_A',
          total_sent: 50,
          total_received: 48,
          total_settled: 47,
          total_dropped: 1,
          total_cost_cents: 125000,
          avg_balance_cents: 950000,
          peak_overdraft_cents: -50000,
          credit_limit_cents: 100000,
          daily_metrics: [
            {
              day: 1,
              sent: 10,
              received: 9,
              settled: 9,
              dropped: 0,
              end_balance_cents: 990000,
              avg_balance_cents: 995000,
            },
            {
              day: 2,
              sent: 10,
              received: 10,
              settled: 10,
              dropped: 0,
              end_balance_cents: 1000000,
              avg_balance_cents: 995000,
            },
          ],
          collateral_events: [],
        }),
      })
    })

    // Navigate to dashboard
    await page.goto('/simulations/sim-001')

    // Click on BANK_A link
    await page.getByRole('link', { name: 'BANK_A' }).click()

    // Verify we're on the agent detail page
    await expect(page).toHaveURL(/\/simulations\/sim-001\/agents\/BANK_A/)

    // Verify agent heading
    await expect(page.getByRole('heading', { name: /BANK_A/i })).toBeVisible()
  })

  test('displays agent summary metrics', async ({ page }) => {
    // Mock agent timeline API
    await page.route('**/api/simulations/sim-001/agents/BANK_A/timeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_id: 'BANK_A',
          total_sent: 50,
          total_received: 48,
          total_settled: 47,
          total_dropped: 1,
          total_cost_cents: 125000,
          avg_balance_cents: 950000,
          peak_overdraft_cents: -50000,
          credit_limit_cents: 100000,
          daily_metrics: [
            {
              day: 1,
              opening_balance: 1000000,
              closing_balance: 950000,
              min_balance: 900000,
              max_balance: 1000000,
              transactions_sent: 10,
              transactions_received: 8,
              total_cost_cents: 5000,
            },
          ],
          collateral_events: [],
        }),
      })
    })

    // Navigate directly to agent page
    await page.goto('/simulations/sim-001/agents/BANK_A')

    // Verify Summary Metrics section header
    await expect(page.getByRole('heading', { name: /summary metrics/i })).toBeVisible()

    // Verify summary metrics are displayed
    await expect(page.getByText(/total sent:/i)).toBeVisible()
    await expect(page.getByText(/total received:/i)).toBeVisible()
    await expect(page.getByText(/total settled:/i)).toBeVisible()
    await expect(page.getByText(/total dropped:/i)).toBeVisible()

    // Verify Balance Metrics section header
    await expect(page.getByRole('heading', { name: /balance metrics/i })).toBeVisible()

    // Verify balance metrics are displayed
    await expect(page.getByText(/average balance:/i)).toBeVisible()
    await expect(page.getByText(/peak overdraft:/i)).toBeVisible()
    await expect(page.getByText(/credit limit:/i)).toBeVisible()
  })

  test('displays daily metrics table', async ({ page }) => {
    // Mock agent timeline API
    await page.route('**/api/simulations/sim-001/agents/BANK_A/timeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_id: 'BANK_A',
          total_sent: 50,
          total_received: 48,
          total_settled: 47,
          total_dropped: 1,
          total_cost_cents: 125000,
          avg_balance_cents: 950000,
          peak_overdraft_cents: -50000,
          credit_limit_cents: 100000,
          daily_metrics: [
            {
              day: 1,
              sent: 10,
              received: 9,
              settled: 9,
              dropped: 0,
              end_balance_cents: 990000,
              avg_balance_cents: 995000,
            },
            {
              day: 2,
              sent: 12,
              received: 11,
              settled: 11,
              dropped: 0,
              end_balance_cents: 980000,
              avg_balance_cents: 985000,
            },
            {
              day: 3,
              sent: 8,
              received: 10,
              settled: 10,
              dropped: 0,
              end_balance_cents: 1000000,
              avg_balance_cents: 990000,
            },
          ],
          collateral_events: [],
        }),
      })
    })

    // Navigate to agent page
    await page.goto('/simulations/sim-001/agents/BANK_A')

    // Verify daily metrics section header
    await expect(page.getByRole('heading', { name: /daily metrics/i })).toBeVisible()

    // Verify table exists and has correct number of rows (3 days)
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await expect(table.locator('tbody tr')).toHaveCount(3)
  })

  test('displays collateral events when present', async ({ page }) => {
    // Mock agent timeline API with collateral events
    await page.route('**/api/simulations/sim-001/agents/BANK_B/timeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_id: 'BANK_B',
          total_sent: 50,
          total_received: 48,
          total_settled: 47,
          total_dropped: 1,
          total_cost_cents: 125000,
          avg_balance_cents: 950000,
          peak_overdraft_cents: -50000,
          credit_limit_cents: 100000,
          daily_metrics: [
            {
              day: 1,
              opening_balance: 1000000,
              closing_balance: 950000,
              min_balance: 900000,
              max_balance: 1000000,
              transactions_sent: 10,
              transactions_received: 8,
              total_cost_cents: 5000,
            },
          ],
          collateral_events: [
            {
              tick: 50,
              event_type: 'pledge',
              amount_cents: 500000,
            },
            {
              tick: 150,
              event_type: 'release',
              amount_cents: 500000,
            },
          ],
        }),
      })
    })

    // Navigate to agent page
    await page.goto('/simulations/sim-001/agents/BANK_B')

    // Verify collateral events section header
    await expect(page.getByRole('heading', { name: /collateral events/i })).toBeVisible()

    // Verify table exists and has correct number of rows (2 events)
    const tables = page.locator('table')
    await expect(tables.nth(1)).toBeVisible() // Second table is collateral events
    await expect(tables.nth(1).locator('tbody tr')).toHaveCount(2)
  })

  test('navigates back to simulation dashboard', async ({ page }) => {
    // Mock agent timeline API
    await page.route('**/api/simulations/sim-001/agents/BANK_A/timeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_id: 'BANK_A',
          total_sent: 50,
          total_received: 48,
          total_settled: 47,
          total_dropped: 1,
          total_cost_cents: 125000,
          avg_balance_cents: 950000,
          peak_overdraft_cents: -50000,
          credit_limit_cents: 100000,
          daily_metrics: [
            {
              day: 1,
              opening_balance: 1000000,
              closing_balance: 950000,
              min_balance: 900000,
              max_balance: 1000000,
              transactions_sent: 10,
              transactions_received: 8,
              total_cost_cents: 5000,
            },
          ],
          collateral_events: [],
        }),
      })
    })

    // Mock simulation detail for back navigation
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

    // Navigate to agent page
    await page.goto('/simulations/sim-001/agents/BANK_A')

    // Click back link
    await page.getByRole('link', { name: /back/i }).click()

    // Verify we're back on the dashboard
    await expect(page).toHaveURL('/simulations/sim-001')
    await expect(page.getByRole('heading', { name: /simulation dashboard/i })).toBeVisible()
  })
})
