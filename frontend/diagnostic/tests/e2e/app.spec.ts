import { test, expect } from '@playwright/test'

test.describe('App Initialization', () => {
  test('loads the homepage', async ({ page }) => {
    await page.goto('/')

    // Verify the page title
    await expect(page).toHaveTitle(/Diagnostic Client/i)

    // Verify header is visible
    await expect(page.locator('header')).toBeVisible()

    // Verify main content area exists
    await expect(page.locator('main')).toBeVisible()
  })

  test('displays diagnostic client heading', async ({ page }) => {
    await page.goto('/')

    // Check for the application heading
    const heading = page.locator('h1')
    await expect(heading).toContainText('Diagnostic Client')
  })
})
