import { test, expect } from '@playwright/test'

test.describe('Transaction Tracing Flow', () => {
  test('navigates from event timeline to transaction detail', async ({ page }) => {
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
          ],
          total: 2,
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
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              details: {},
            },
            {
              tick: 15,
              event_type: 'Settlement',
              details: { method: 'rtgs' },
            },
          ],
          related_transactions: [],
        }),
      })
    })

    // Navigate to events page
    await page.goto('/simulations/sim-001/events')

    // Wait for events to load
    await expect(page.getByText('Arrival')).toBeVisible()

    // Click on transaction link (first occurrence if there are multiple)
    await page.getByRole('link', { name: 'tx-001' }).first().click()

    // Verify we're on transaction detail page
    await expect(page).toHaveURL(/\/simulations\/sim-001\/transactions\/tx-001/)
    await expect(page.locator('main h1')).toContainText('Transaction: tx-001')
  })

  test('displays transaction details and status', async ({ page }) => {
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
            settlement_tick: 25,
            status: 'settled',
            delay_cost: 150,
            amount_settled: 100000,
          },
          events: [],
          related_transactions: [],
        }),
      })
    })

    // Navigate to transaction page
    await page.goto('/simulations/sim-001/transactions/tx-001')

    // Verify transaction ID in heading (within main content)
    await expect(page.locator('main h1')).toContainText('Transaction: tx-001')

    // Verify Details section header
    await expect(page.getByRole('heading', { name: /details/i })).toBeVisible()

    // Verify status badge
    await expect(page.getByRole('status')).toHaveText('settled')

    // Verify sender and receiver labels
    await expect(page.getByText('From', { exact: true })).toBeVisible()
    await expect(page.getByText('BANK_A')).toBeVisible()
    await expect(page.getByText('To', { exact: true })).toBeVisible()
    await expect(page.getByText('BANK_B')).toBeVisible()

    // Verify key fields are present
    await expect(page.getByText('Amount', { exact: true })).toBeVisible()
    await expect(page.getByText('Priority', { exact: true })).toBeVisible()
    await expect(page.getByText('Arrival', { exact: true })).toBeVisible()
    await expect(page.getByText('Deadline', { exact: true })).toBeVisible()
    await expect(page.getByText('Settlement', { exact: true })).toBeVisible()
  })

  test('displays transaction event timeline', async ({ page }) => {
    // Mock transaction lifecycle API
    await page.route('**/api/simulations/sim-001/transactions/tx-002/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-002',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            arrival_tick: 10,
            deadline_tick: 50,
            settlement_tick: 25,
            status: 'settled',
            delay_cost: 150,
            amount_settled: 100000,
          },
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              details: {},
            },
            {
              tick: 15,
              event_type: 'PolicyHold',
              details: { reason: 'insufficient_liquidity' },
            },
            {
              tick: 20,
              event_type: 'LSMAttempt',
              details: { offset_found: false },
            },
            {
              tick: 25,
              event_type: 'Settlement',
              details: { method: 'rtgs' },
            },
          ],
          related_transactions: [],
        }),
      })
    })

    // Navigate to transaction page
    await page.goto('/simulations/sim-001/transactions/tx-002')

    // Verify event timeline section header
    await expect(page.getByRole('heading', { name: /event timeline/i })).toBeVisible()

    // Verify all event types are displayed (may appear multiple times in text)
    const pageContent = page.locator('body')
    await expect(pageContent).toContainText('Arrival')
    await expect(pageContent).toContainText('PolicyHold')
    await expect(pageContent).toContainText('LSMAttempt')
    await expect(pageContent).toContainText('Settlement')
  })

  test('displays related transactions when split', async ({ page }) => {
    // Mock transaction lifecycle API with split parts
    await page.route('**/api/simulations/sim-001/transactions/tx-003/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-003',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            arrival_tick: 10,
            deadline_tick: 50,
            settlement_tick: null,
            status: 'split',
            delay_cost: 0,
            amount_settled: 0,
          },
          events: [
            {
              tick: 10,
              event_type: 'Arrival',
              details: {},
            },
            {
              tick: 20,
              event_type: 'Split',
              details: { num_parts: 2 },
            },
          ],
          related_transactions: [
            {
              tx_id: 'tx-003-1',
              relationship: 'split_part',
              split_index: 1,
            },
            {
              tx_id: 'tx-003-2',
              relationship: 'split_part',
              split_index: 2,
            },
          ],
        }),
      })
    })

    // Navigate to transaction page
    await page.goto('/simulations/sim-001/transactions/tx-003')

    // Verify related transactions section header
    await expect(page.getByRole('heading', { name: /related transactions/i })).toBeVisible()

    // Verify split parts are shown as links
    await expect(page.getByRole('link', { name: 'tx-003-1' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'tx-003-2' })).toBeVisible()
  })

  test('displays cost breakdown', async ({ page }) => {
    // Mock transaction lifecycle API
    await page.route('**/api/simulations/sim-001/transactions/tx-004/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-004',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            arrival_tick: 10,
            deadline_tick: 50,
            settlement_tick: 45,
            status: 'settled',
            delay_cost: 350,
            amount_settled: 100000,
          },
          events: [],
          related_transactions: [],
        }),
      })
    })

    // Navigate to transaction page
    await page.goto('/simulations/sim-001/transactions/tx-004')

    // Verify cost breakdown section header
    await expect(page.getByRole('heading', { name: /cost breakdown/i })).toBeVisible()

    // Verify delay cost is shown
    await expect(page.getByText(/delay cost:/i)).toBeVisible()
  })

  test('navigates to related transaction detail', async ({ page }) => {
    // Mock parent transaction
    await page.route('**/api/simulations/sim-001/transactions/tx-005/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-005',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 100000,
            priority: 5,
            arrival_tick: 10,
            deadline_tick: 50,
            settlement_tick: null,
            status: 'split',
            delay_cost: 0,
            amount_settled: 0,
          },
          events: [],
          related_transactions: [
            {
              tx_id: 'tx-005-1',
              relationship: 'split_part',
              split_index: 1,
            },
          ],
        }),
      })
    })

    // Mock split part transaction
    await page.route('**/api/simulations/sim-001/transactions/tx-005-1/lifecycle', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          transaction: {
            tx_id: 'tx-005-1',
            sender_id: 'BANK_A',
            receiver_id: 'BANK_B',
            amount: 50000,
            priority: 5,
            arrival_tick: 20,
            deadline_tick: 50,
            settlement_tick: 25,
            status: 'settled',
            delay_cost: 50,
            amount_settled: 50000,
          },
          events: [],
          related_transactions: [
            {
              tx_id: 'tx-005',
              relationship: 'parent',
            },
          ],
        }),
      })
    })

    // Navigate to parent transaction
    await page.goto('/simulations/sim-001/transactions/tx-005')

    // Click on related transaction link
    await page.getByRole('link', { name: 'tx-005-1' }).click()

    // Verify we're on the split part detail page
    await expect(page).toHaveURL(/\/simulations\/sim-001\/transactions\/tx-005-1/)
    await expect(page.locator('main h1')).toContainText('Transaction: tx-005-1')
    await expect(page.getByRole('status')).toHaveText('settled')
  })

  test('navigates back to simulation dashboard', async ({ page }) => {
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
            settlement_tick: 25,
            status: 'settled',
            delay_cost: 150,
            amount_settled: 100000,
          },
          events: [],
          related_transactions: [],
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

    // Navigate to transaction page
    await page.goto('/simulations/sim-001/transactions/tx-001')

    // Click back link (goes to events page, not dashboard)
    await page.getByRole('link', { name: /back to events/i }).click()

    // Verify we're on the events page
    await expect(page).toHaveURL('/simulations/sim-001/events')
  })
})
