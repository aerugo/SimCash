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
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
                priority: 5,
                deadline_tick: 50,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-2',
              simulation_id: 'sim-001',
              tick: 15,
              day: 0,
              event_type: 'Settlement',
              event_timestamp: '2024-01-01T00:00:15Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-3',
              simulation_id: 'sim-001',
              tick: 20,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:20Z',
              details: {
                sender_id: 'BANK_B',
                receiver_id: 'BANK_A',
                amount: 50000,
                priority: 3,
                deadline_tick: 60,
              },
              tx_id: 'tx-002',
              created_at: '2024-01-01T00:00:00Z',
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
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
                priority: 5,
                deadline_tick: 50,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-2',
              simulation_id: 'sim-001',
              tick: 15,
              day: 0,
              event_type: 'Settlement',
              event_timestamp: '2024-01-01T00:00:15Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-3',
              simulation_id: 'sim-001',
              tick: 20,
              day: 0,
              event_type: 'PolicyDrop',
              event_timestamp: '2024-01-01T00:00:20Z',
              details: {
                sender_id: 'BANK_B',
                receiver_id: 'BANK_C',
                amount: 200000,
              },
              tx_id: 'tx-002',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-4',
              simulation_id: 'sim-001',
              tick: 25,
              day: 0,
              event_type: 'PolicyHold',
              event_timestamp: '2024-01-01T00:00:25Z',
              details: {
                sender_id: 'BANK_C',
                receiver_id: 'BANK_A',
                amount: 150000,
              },
              tx_id: 'tx-003',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-5',
              simulation_id: 'sim-001',
              tick: 30,
              day: 0,
              event_type: 'LsmBilateralOffset',
              event_timestamp: '2024-01-01T00:00:30Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 75000,
              },
              tx_id: 'tx-004',
              created_at: '2024-01-01T00:00:00Z',
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
    await expect(pageContent).toContainText('PolicyDrop')
    await expect(pageContent).toContainText('PolicyHold')
    await expect(pageContent).toContainText('LsmBilateralOffset')

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
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
                priority: 5,
                deadline_tick: 50,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
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
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {
                sender_id: 'BANK_A',
                receiver_id: 'BANK_B',
                amount: 100000,
                priority: 5,
                deadline_tick: 50,
              },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
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

test.describe('Event Timeline Filtering', () => {
  test('filters events by tick range', async ({ page }) => {
    // Mock events with dynamic query parameter handling
    await page.route('**/api/simulations/sim-001/events**', async (route) => {
      const url = new URL(route.request().url())
      const params = url.searchParams

      const tickMin = params.get('tick_min')
      const tickMax = params.get('tick_max')

      if (tickMin === '10' && tickMax === '20') {
        // Filtered response
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [
              {
                event_id: 'evt-2',
                simulation_id: 'sim-001',
                tick: 15,
                day: 0,
                event_type: 'Settlement',
                event_timestamp: '2024-01-01T00:00:15Z',
                details: { tx_id: 'tx-001', amount: 100000 },
                tx_id: 'tx-001',
                created_at: '2024-01-01T00:00:00Z',
              },
            ],
            total: 1,
            limit: 100,
            offset: 0,
            filters: {
              tick_min: 10,
              tick_max: 20,
            },
          }),
        })
      } else {
        // Unfiltered response
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [
              {
                event_id: 'evt-1',
                simulation_id: 'sim-001',
                tick: 5,
                day: 0,
                event_type: 'Arrival',
                event_timestamp: '2024-01-01T00:00:05Z',
                details: { sender_id: 'BANK_A', receiver_id: 'BANK_B', amount: 100000 },
                tx_id: 'tx-001',
                created_at: '2024-01-01T00:00:00Z',
              },
              {
                event_id: 'evt-2',
                simulation_id: 'sim-001',
                tick: 15,
                day: 0,
                event_type: 'Settlement',
                event_timestamp: '2024-01-01T00:00:15Z',
                details: { tx_id: 'tx-001', amount: 100000 },
                tx_id: 'tx-001',
                created_at: '2024-01-01T00:00:00Z',
              },
            ],
            total: 2,
            limit: 100,
            offset: 0,
          }),
        })
      }
    })

    await page.goto('/simulations/sim-001/events')

    // Open filters (if collapsed)
    await page.getByRole('button', { name: /filters/i }).click()

    // Set tick range
    await page.getByLabel(/min tick/i).fill('10')
    await page.getByLabel(/max tick/i).fill('20')

    // Apply filters
    await page.getByRole('button', { name: /apply/i }).click()

    // Verify only filtered event is shown
    await expect(page.getByText('Tick 15')).toBeVisible()
    await expect(page.getByText('Tick 5')).not.toBeVisible()
  })

  // TODO: Implement agent filtering feature and re-enable these tests
  // test('filters events by agent', async ({ page }) => { ... })
  // test('filters events by event type', async ({ page }) => { ... })

  test('clears all filters', async ({ page }) => {
    // Mock events with dynamic parameter handling
    await page.route('**/api/simulations/sim-001/events**', async (route) => {
      const url = new URL(route.request().url())
      const params = url.searchParams

      const tickMin = params.get('tick_min')
      const agentId = params.get('agent_id')

      if (tickMin === '10' && agentId === 'BANK_A') {
        // Return filtered events
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [{
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            }],
            total: 1,
            limit: 100,
            offset: 0,
            filters: { tick_min: 10, agent_id: 'BANK_A' },
          }),
        })
      } else {
        // Return unfiltered events
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [
              {
                event_id: 'evt-1',
                simulation_id: 'sim-001',
                tick: 10,
                day: 0,
                event_type: 'Arrival',
                event_timestamp: '2024-01-01T00:00:10Z',
                details: {},
                created_at: '2024-01-01T00:00:00Z',
              },
              {
                event_id: 'evt-2',
                simulation_id: 'sim-001',
                tick: 20,
                day: 0,
                event_type: 'Settlement',
                event_timestamp: '2024-01-01T00:00:20Z',
                details: {},
                created_at: '2024-01-01T00:00:00Z',
              },
            ],
            total: 2,
            limit: 100,
            offset: 0,
          }),
        })
      }
    })

    await page.goto('/simulations/sim-001/events?tick_min=10&agent_id=BANK_A')

    // Open filters
    await page.getByRole('button', { name: /filters/i }).click()

    // Click clear filters
    await page.getByRole('button', { name: /clear/i }).click()

    // Verify all events are shown
    await expect(page.getByText('Tick 10')).toBeVisible()
    await expect(page.getByText('Tick 20')).toBeVisible()
  })

  // TODO: Implement agent filtering and re-enable
  // test('updates URL with filter parameters', async ({ page }) => { ... })
})

test.describe('Event Timeline Keyboard Shortcuts', () => {
  test('navigates through events with j/k keys', async ({ page }) => {
    // Mock events API with multiple events
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: { sender_id: 'BANK_A', receiver_id: 'BANK_B', amount: 100000 },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-2',
              simulation_id: 'sim-001',
              tick: 15,
              day: 0,
              event_type: 'Settlement',
              event_timestamp: '2024-01-01T00:00:15Z',
              details: { tx_id: 'tx-001', amount: 100000 },
              tx_id: 'tx-001',
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-3',
              simulation_id: 'sim-001',
              tick: 20,
              day: 0,
              event_type: 'PolicyHold',
              event_timestamp: '2024-01-01T00:00:20Z',
              details: { tx_id: 'tx-002', amount: 50000 },
              tx_id: 'tx-002',
              created_at: '2024-01-01T00:00:00Z',
            },
          ],
          total: 3,
          limit: 100,
          offset: 0,
        }),
      })
    })

    await page.goto('/simulations/sim-001/events')

    // Wait for events to load
    await expect(page.getByText('Tick 10')).toBeVisible()

    // Press 'j' to navigate down (should highlight evt-1 initially, then evt-2)
    await page.keyboard.press('j')

    // Verify first event has focus/highlight
    const firstEvent = page.locator('[data-event-id="evt-1"]')
    await expect(firstEvent).toHaveClass(/event-selected/)

    // Press 'j' again to move to second event
    await page.keyboard.press('j')
    const secondEvent = page.locator('[data-event-id="evt-2"]')
    await expect(secondEvent).toHaveClass(/event-selected/)
    await expect(firstEvent).not.toHaveClass(/event-selected/)

    // Press 'k' to move back up to first event
    await page.keyboard.press('k')
    await expect(firstEvent).toHaveClass(/event-selected/)
    await expect(secondEvent).not.toHaveClass(/event-selected/)
  })

  test('j key does not navigate past last event', async ({ page }) => {
    // Mock events with only 2 events
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-2',
              simulation_id: 'sim-001',
              tick: 15,
              day: 0,
              event_type: 'Settlement',
              event_timestamp: '2024-01-01T00:00:15Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            },
          ],
          total: 2,
          limit: 100,
          offset: 0,
        }),
      })
    })

    await page.goto('/simulations/sim-001/events')
    await expect(page.getByText('Tick 10')).toBeVisible()

    // Navigate to last event
    await page.keyboard.press('j')
    await page.keyboard.press('j')

    const lastEvent = page.locator('[data-event-id="evt-2"]')
    await expect(lastEvent).toHaveClass(/event-selected/)

    // Try to navigate past last event
    await page.keyboard.press('j')

    // Should still be on last event
    await expect(lastEvent).toHaveClass(/event-selected/)
  })

  test('k key does not navigate past first event', async ({ page }) => {
    // Mock events
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [
            {
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            },
            {
              event_id: 'evt-2',
              simulation_id: 'sim-001',
              tick: 15,
              day: 0,
              event_type: 'Settlement',
              event_timestamp: '2024-01-01T00:00:15Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            },
          ],
          total: 2,
          limit: 100,
          offset: 0,
        }),
      })
    })

    await page.goto('/simulations/sim-001/events')
    await expect(page.getByText('Tick 10')).toBeVisible()

    // Try to navigate up when already at first event
    await page.keyboard.press('k')

    // First event should not have selection (or should remain unselected)
    const firstEvent = page.locator('[data-event-id="evt-1"]')
    await expect(firstEvent).not.toHaveClass(/event-selected/)
  })

  test('focuses filter input with / key', async ({ page }) => {
    // Mock events
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [{
            event_id: 'evt-1',
            simulation_id: 'sim-001',
            tick: 10,
            day: 0,
            event_type: 'Arrival',
            event_timestamp: '2024-01-01T00:00:10Z',
            details: {},
            created_at: '2024-01-01T00:00:00Z',
          }],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      })
    })

    await page.goto('/simulations/sim-001/events')
    await expect(page.getByText('Tick 10')).toBeVisible()

    // Press '/' to open filters and focus first input
    await page.keyboard.press('/')

    // Verify filters panel is open
    await expect(page.getByLabel(/min tick/i)).toBeVisible()

    // Verify first filter input has focus
    await expect(page.getByLabel(/min tick/i)).toBeFocused()
  })

  test('clears filters with Esc key', async ({ page }) => {
    // Mock all variations of filtered and unfiltered routes (parameter order may vary)
    await page.route('**/api/simulations/sim-001/events**', async (route) => {
      const url = new URL(route.request().url())
      const params = url.searchParams

      const hasTickMin = params.has('tick_min')
      const tickMin = params.get('tick_min')

      if (hasTickMin && tickMin === '10') {
        // Filtered response
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [{
              event_id: 'evt-1',
              simulation_id: 'sim-001',
              tick: 10,
              day: 0,
              event_type: 'Arrival',
              event_timestamp: '2024-01-01T00:00:10Z',
              details: {},
              created_at: '2024-01-01T00:00:00Z',
            }],
            total: 1,
            limit: 100,
            offset: 0,
            filters: { tick_min: 10 },
          }),
        })
      } else {
        // Unfiltered response
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            events: [
              {
                event_id: 'evt-1',
                simulation_id: 'sim-001',
                tick: 10,
                day: 0,
                event_type: 'Arrival',
                event_timestamp: '2024-01-01T00:00:10Z',
                details: {},
                created_at: '2024-01-01T00:00:00Z',
              },
              {
                event_id: 'evt-2',
                simulation_id: 'sim-001',
                tick: 5,
                day: 0,
                event_type: 'Settlement',
                event_timestamp: '2024-01-01T00:00:05Z',
                details: {},
                created_at: '2024-01-01T00:00:00Z',
              },
            ],
            total: 2,
            limit: 100,
            offset: 0,
          }),
        })
      }
    })

    // Start with filtered URL
    await page.goto('/simulations/sim-001/events?tick_min=10')

    // Verify filter is active (should show 1 event)
    await expect(page.getByText('Showing 1-1 of 1')).toBeVisible()

    // Press Esc to clear filters
    await page.keyboard.press('Escape')

    // Verify all events are shown (2 events)
    await expect(page.getByText('Showing 1-2 of 2')).toBeVisible()
    await expect(page.getByText('Tick 5')).toBeVisible()
  })

  test('keyboard shortcuts do not interfere with input fields', async ({ page }) => {
    // Mock events
    await page.route('**/api/simulations/sim-001/events?limit=100&offset=0', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [{
            event_id: 'evt-1',
            simulation_id: 'sim-001',
            tick: 10,
            day: 0,
            event_type: 'Arrival',
            event_timestamp: '2024-01-01T00:00:10Z',
            details: {},
            created_at: '2024-01-01T00:00:00Z',
          }],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      })
    })

    await page.goto('/simulations/sim-001/events')

    // Open filters
    await page.getByRole('button', { name: /filters/i }).click()

    // Focus on transaction ID input (text input that accepts any characters)
    const txIdInput = page.getByLabel(/transaction id/i)
    await txIdInput.click()

    // Type 'jk' - should type into input, not navigate
    await page.keyboard.type('jk')

    // Verify input contains 'jk' (proves shortcut didn't trigger)
    await expect(txIdInput).toHaveValue('jk')
  })
})
