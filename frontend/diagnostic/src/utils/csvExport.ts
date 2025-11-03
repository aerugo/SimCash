import type { EventRecord } from '@/types/api'

/**
 * Export events to CSV format
 *
 * Converts event records to CSV format suitable for analysis in spreadsheet tools.
 * Flattens the details object into separate columns for easier analysis.
 */
export function exportEventsToCSV(events: EventRecord[], filename: string = 'events.csv'): void {
  if (events.length === 0) {
    alert('No events to export')
    return
  }

  // Collect all unique detail keys across all events
  const detailKeys = new Set<string>()
  events.forEach(event => {
    Object.keys(event.details).forEach(key => detailKeys.add(key))
  })

  // Define CSV headers
  const baseHeaders = [
    'event_id',
    'simulation_id',
    'tick',
    'day',
    'event_type',
    'event_timestamp',
    'agent_id',
    'tx_id',
    'created_at',
  ]

  const detailHeaders = Array.from(detailKeys).sort()
  const headers = [...baseHeaders, ...detailHeaders]

  // Convert events to CSV rows
  const rows = events.map(event => {
    const baseValues = [
      event.event_id,
      event.simulation_id,
      event.tick,
      event.day,
      event.event_type,
      event.event_timestamp,
      event.agent_id || '',
      event.tx_id || '',
      event.created_at,
    ]

    // Add detail values in same order as headers
    const detailValues = detailHeaders.map(key => {
      const value = event.details[key]
      if (value === null || value === undefined) {
        return ''
      }
      // Handle objects/arrays by converting to JSON string
      if (typeof value === 'object') {
        return JSON.stringify(value)
      }
      return String(value)
    })

    return [...baseValues, ...detailValues]
  })

  // Escape CSV values (handle commas, quotes, newlines)
  const escapeCSV = (value: string | number): string => {
    const str = String(value)
    // If value contains comma, quote, or newline, wrap in quotes and escape quotes
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`
    }
    return str
  }

  // Build CSV content
  const csvContent = [
    headers.map(escapeCSV).join(','),
    ...rows.map(row => row.map(escapeCSV).join(',')),
  ].join('\n')

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  URL.revokeObjectURL(url)
}

/**
 * Generate a default filename for CSV export
 */
export function generateCSVFilename(simulationId: string, filters?: Record<string, any>): string {
  const timestamp = new Date().toISOString().split('T')[0] // YYYY-MM-DD
  const filterStr = filters && Object.keys(filters).length > 0 ? '_filtered' : ''
  return `events_${simulationId}${filterStr}_${timestamp}.csv`
}
