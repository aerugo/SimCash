import { describe, it, expect } from 'vitest'
import { formatCurrency, formatCurrencyShort } from '../currency'

describe('formatCurrency', () => {
  it('formats positive amounts correctly', () => {
    expect(formatCurrency(100000)).toBe('$1,000.00')
    expect(formatCurrency(50)).toBe('$0.50')
    expect(formatCurrency(1)).toBe('$0.01')
  })

  it('formats negative amounts correctly', () => {
    expect(formatCurrency(-100000)).toBe('-$1,000.00')
  })

  it('formats zero correctly', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('handles large amounts', () => {
    expect(formatCurrency(1234567890)).toBe('$12,345,678.90')
  })
})

describe('formatCurrencyShort', () => {
  it('formats millions with M suffix', () => {
    expect(formatCurrencyShort(150000000)).toBe('$1.5M')
  })

  it('formats thousands with K suffix', () => {
    expect(formatCurrencyShort(250000)).toBe('$2.5K')
  })

  it('formats small amounts without suffix', () => {
    expect(formatCurrencyShort(50000)).toBe('$500.00')
  })
})
