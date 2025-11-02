const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

/** API error with status code */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public response?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Base fetch wrapper with error handling */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        (error as { message?: string }).message || `HTTP ${response.status}`,
        response.status,
        error
      )
    }

    return response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Network error', 0, error)
  }
}

/** GET request helper */
export async function apiGet<T>(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> {
  const query = params
    ? '?' +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : ''

  return apiFetch<T>(`${endpoint}${query}`)
}
