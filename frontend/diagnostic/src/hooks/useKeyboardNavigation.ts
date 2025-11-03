import { useEffect, useCallback } from 'react'

export interface KeyboardNavigationOptions {
  onNavigateDown?: () => void
  onNavigateUp?: () => void
  onFocusFilter?: () => void
  onClearFilters?: () => void
  enabled?: boolean
}

/**
 * Custom hook for keyboard navigation on event timeline page
 *
 * Keyboard shortcuts:
 * - j: Navigate down through events
 * - k: Navigate up through events
 * - /: Focus filter input
 * - Esc: Clear all filters
 *
 * Shortcuts are disabled when user is typing in input fields or textareas
 */
export function useKeyboardNavigation({
  onNavigateDown,
  onNavigateUp,
  onFocusFilter,
  onClearFilters,
  enabled = true,
}: KeyboardNavigationOptions) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return

      // Don't trigger shortcuts when user is typing in an input or textarea
      const target = event.target as HTMLElement
      const isInputField =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable

      if (isInputField) {
        // Only handle Escape in input fields (to clear/blur)
        if (event.key === 'Escape' && onClearFilters) {
          event.preventDefault()
          onClearFilters()
        }
        return
      }

      // Handle keyboard shortcuts
      switch (event.key) {
        case 'j':
          event.preventDefault()
          onNavigateDown?.()
          break

        case 'k':
          event.preventDefault()
          onNavigateUp?.()
          break

        case '/':
          event.preventDefault()
          onFocusFilter?.()
          break

        case 'Escape':
          event.preventDefault()
          onClearFilters?.()
          break

        default:
          break
      }
    },
    [enabled, onNavigateDown, onNavigateUp, onFocusFilter, onClearFilters]
  )

  useEffect(() => {
    if (!enabled) return

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [enabled, handleKeyDown])
}
