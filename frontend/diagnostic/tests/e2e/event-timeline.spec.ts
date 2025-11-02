import { test, expect } from '@playwright/test'

test.describe('Event Timeline Navigation', () => {
  test('navigates from dashboard to event timeline', async ({ page }) => {
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

    // Mock events API
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

    // Navigate to dashboard
    await page.goto('/simulations/sim-001')

    // Click "View Events" link
    await page.getByRole('link', { name: /events/i }).click()

    // Verify we're on the events page
    await expect(page).toHaveURL(/\/simulations\/sim-001\/events/)
    await expect(page.getByRole('heading', { name: /event timeline/i })).toBeVisible()
  })

  test('displays paginated event list', async ({ page }) => {
    // Mock events API
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
              priority: 5,
              deadline_tick: 50,
            },
            {
              tick: 15,
              event_type: 'Settlement',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
            },
            {
              tick: 20,
              event_type: 'Arrival',
              tx_id: 'tx-002',
              sender_id: 'BANK_B',
              receiver_id: 'BANK_A',
              amount: 50000,
              priority: 3,
              deadline_tick: 60,
            },
          ],
          total: 250,
          limit: 100,
          offset: 0,
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Verify pagination info exists
    await expect(page.getByText(/showing/i)).toBeVisible()
    await expect(page.getByText(/250/)).toBeVisible() // total count

    // Verify events are displayed
    const pageContent = page.locator('body')
    await expect(pageContent).toContainText('Arrival')
    await expect(pageContent).toContainText('Settlement')

    // Verify tick numbers are shown
    await expect(pageContent).toContainText('Tick 10')
    await expect(pageContent).toContainText('Tick 15')
    await expect(pageContent).toContainText('Tick 20')
  })

  test('displays event details with color-coded badges', async ({ page }) => {
    // Mock events API with different event types
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
              priority: 5,
              deadline_tick: 50,
            },
            {
              tick: 15,
              event_type: 'Settlement',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
            },
            {
              tick: 20,
              event_type: 'Drop',
              tx_id: 'tx-002',
              sender_id: 'BANK_B',
              receiver_id: 'BANK_C',
              amount: 200000,
            },
            {
              tick: 25,
              event_type: 'PolicyHold',
              tx_id: 'tx-003',
              sender_id: 'BANK_C',
              receiver_id: 'BANK_A',
              amount: 150000,
            },
            {
              tick: 30,
              event_type: 'LSMAttempt',
              tx_id: 'tx-004',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 75000,
            },
          ],
          total: 5,
          limit: 100,
          offset: 0,
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Verify all event types are displayed (may appear multiple times)
    const pageContent = page.locator('body')
    await expect(pageContent).toContainText('Arrival')
    await expect(pageContent).toContainText('Settlement')
    await expect(pageContent).toContainText('Drop')
    await expect(pageContent).toContainText('PolicyHold')
    await expect(pageContent).toContainText('LSMAttempt')

    // Verify sender/receiver info is present (appears multiple times)
    await expect(pageContent).toContainText('BANK_A')
    await expect(pageContent).toContainText('BANK_B')
    await expect(pageContent).toContainText('BANK_C')
  })

  test('displays transaction details for each event', async ({ page }) => {
    // Mock events API
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
              priority: 5,
              deadline_tick: 50,
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Verify transaction ID is a link
    await expect(page.getByRole('link', { name: 'tx-001' })).toBeVisible()

    // Verify transaction details are displayed
    const pageContent = page.locator('body')
    await expect(pageContent).toContainText('$1,000.00')
    await expect(pageContent).toContainText('Priority')
    await expect(pageContent).toContainText('Deadline')
    await expect(pageContent).toContainText('Tick 50')
  })

  test('links to transaction detail page', async ({ page }) => {
    // Mock events API
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              tx_id: 'tx-001',
              sender_id: 'BANK_A',
              receiver_id: 'BANK_B',
              amount: 100000,
              priority: 5,
              deadline_tick: 50,
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      })
    })

    // Mock transaction lifecycle API
    await page.route('**/api/simulations/sim-001/transactions/tx-001/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-001',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            arrival_tick: 10,
            deadline_tick: 50,
            settlement_tick: 15,
            status: 'settled',
            delay_cost: 50,
            amount_settled: 100000,
          },
          events: [],
          related_transactions: [],
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Click transaction link
    await page.getByRole('link', { name: 'tx-001' }).click()

    // Verify we're on transaction detail page
    await expect(page).toHaveURL(/\/simulations\/sim-001\/transactions\/tx-001/)
  })

  test('shows empty state when no events', async ({ page }) => {
    // Mock events API with empty result
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

    // Pagination info should not be displayed when there are no results
    // (The component only shows pagination when total > 0)
  })

  test('navigates back to simulation dashboard', async ({ page }) => {
    // Mock events API
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

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Click back link
    await page.getByRole('link', { name: /back to simulation/i }).click()

    // Verify we're back on the dashboard
    await expect(page).toHaveURL('/simulations/sim-001')
  })
})
