/**
 * Format cents as currency string
 * @param cents - Amount in cents (i64 from backend)
 * @returns Formatted string like "$1,000.00"
 */
export function formatCurrency(cents: number): string {
  const dollars = cents / 100
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(dollars)
}

/**
 * Format cents as abbreviated currency (for charts)
 * @param cents - Amount in cents
 * @returns Formatted string like "$1.2M" or "$500K"
 */
export function formatCurrencyShort(cents: number): string {
  const dollars = cents / 100

  if (dollars >= 1_000_000) {
    return `$${(dollars / 1_000_000).toFixed(1)}M`
  }
  if (dollars >= 1_000) {
    return `$${(dollars / 1_000).toFixed(1)}K`
  }
  return formatCurrency(cents)
}
