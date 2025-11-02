import { test, expect } from '@playwright/test'

test.describe('Error Handling', () => {
  test('displays error when simulation list API fails', async ({ page }) => {
    // Mock API error
    await page.route('**/api/simulations', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Internal server error',
        }),
      })
    })

    // Navigate to homepage
    await page.goto('/')

    // Verify error message is displayed
    await expect(page.getByText(/error/i)).toBeVisible()
  })

  test('displays error when simulation detail API fails', async ({ page }) => {
    // Mock API error
    await page.route('**/api/simulations/sim-001', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Failed to load simulation',
        }),
      })
    })

    // Navigate to simulation detail
    await page.goto('/simulations/sim-001')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading simulation/i })).toBeVisible()
  })

  test('displays error when agent detail API fails', async ({ page }) => {
    // Mock API error
    await page.route('**/api/simulations/sim-001/agents/BANK_A/timeline', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Failed to load agent data',
        }),
      })
    })

    // Navigate to agent detail
    await page.goto('/simulations/sim-001/agents/BANK_A')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading agent/i })).toBeVisible()
  })

  test('displays error when events API fails', async ({ page }) => {
    // Mock API error
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Failed to load events',
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading events/i })).toBeVisible()
  })

  test('displays error when transaction detail API fails', async ({ page }) => {
    // Mock API error
    await page.route('**/api/simulations/sim-001/transactions/tx-001/lifecycle', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Failed to load transaction',
        }),
      })
    })

    // Navigate to transaction detail
    await page.goto('/simulations/sim-001/transactions/tx-001')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading transaction/i })).toBeVisible()
  })

  test('displays error for 404 not found simulation', async ({ page }) => {
    // Mock 404 response
    await page.route('**/api/simulations/nonexistent-sim', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Simulation not found',
        }),
      })
    })

    // Navigate to non-existent simulation
    await page.goto('/simulations/nonexistent-sim')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading simulation/i })).toBeVisible()
  })

  test('displays error for 404 not found agent', async ({ page }) => {
    // Mock 404 response
    await page.route('**/api/simulations/sim-001/agents/BANK_X/timeline', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Agent not found',
        }),
      })
    })

    // Navigate to non-existent agent
    await page.goto('/simulations/sim-001/agents/BANK_X')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading agent/i })).toBeVisible()
  })

  test('displays error for 404 not found transaction', async ({ page }) => {
    // Mock 404 response
    await page.route('**/api/simulations/sim-001/transactions/tx-999/lifecycle', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Transaction not found',
        }),
      })
    })

    // Navigate to non-existent transaction
    await page.goto('/simulations/sim-001/transactions/tx-999')

    // Verify error message is displayed
    await expect(page.getByRole('heading', { name: /error loading transaction/i })).toBeVisible()
  })

  test('displays empty state when simulation has no data', async ({ page }) => {
    // Mock simulation with empty data
    await page.route('**/api/simulations/sim-empty', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulation_id: 'sim-empty',
          created_at: '2024-01-01T00:00:00Z',
          config: {
            simulation: {
              ticks_per_day: 100,
              num_days: 5,
              rng_seed: 12345,
            },
            agents: [],
          },
          summary: {
            total_ticks: 0,
            total_transactions: 0,
            settlement_rate: 0,
            total_cost_cents: 0,
            duration_seconds: 0,
            ticks_per_second: 0,
          },
        }),
      })
    })

    // Navigate to empty simulation
    await page.goto('/simulations/sim-empty')

    // Verify dashboard loads and shows simulation ID (within main content)
    await expect(page.locator('main h1')).toContainText('Simulation: sim-empty')

    // Verify configuration section is displayed
    await expect(page.getByRole('heading', { name: /configuration/i })).toBeVisible()

    // Verify summary metrics section is displayed
    await expect(page.getByRole('heading', { name: /summary metrics/i })).toBeVisible()
  })

  test('displays empty state when no events exist', async ({ page }) => {
    // Mock empty events response
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [],
          total: 0,
          limit: 100,
          offset: 0,
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Verify empty state message
    await expect(page.getByText(/no events found/i)).toBeVisible()
  })

  test('displays empty state when simulation list is empty', async ({ page }) => {
    // Mock empty simulations response
    await page.route('**/api/simulations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulations: [],
        }),
      })
    })

    // Navigate to homepage
    await page.goto('/')

    // Verify empty state message
    await expect(page.getByText(/no simulations found/i)).toBeVisible()
  })

  test('shows loading state before data loads', async ({ page }) => {
    // Mock slow API response
    await page.route('**/api/simulations', async (route) => {
      // Delay the response
      await new Promise((resolve) => setTimeout(resolve, 1000))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          simulations: [],
        }),
      })
    })

    // Navigate to homepage
    const navigation = page.goto('/')

    // Verify loading state appears
    await expect(page.getByText(/loading/i)).toBeVisible()

    // Wait for navigation to complete
    await navigation
  })

  test('handles network error gracefully', async ({ page }) => {
    // Simulate network failure
    await page.route('**/api/simulations', async (route) => {
      await route.abort('failed')
    })

    // Navigate to homepage
    await page.goto('/')

    // Verify error message is displayed
    await expect(page.getByText(/error/i)).toBeVisible()
  })
})
