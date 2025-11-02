import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { apiFetch, apiGet, ApiError } from '../client'

// Setup MSW server for mocking API calls
const server = setupServer()

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('apiFetch', () => {
  it('makes successful GET request', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', () => {
        return HttpResponse.json({ success: true })
      })
    )

    const result = await apiFetch<{ success: boolean }>('/test')
    expect(result).toEqual({ success: true })
  })

  it('throws ApiError on 404', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', () => {
        return new HttpResponse(null, { status: 404 })
      })
    )

    await expect(apiFetch('/test')).rejects.toThrow(ApiError)
    await expect(apiFetch('/test')).rejects.toHaveProperty('status', 404)
  })

  it('throws ApiError on 500', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', () => {
        return HttpResponse.json(
          { message: 'Internal server error' },
          { status: 500 }
        )
      })
    )

    await expect(apiFetch('/test')).rejects.toThrow(ApiError)
    await expect(apiFetch('/test')).rejects.toHaveProperty('status', 500)
  })

  it('includes error message from response', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', () => {
        return HttpResponse.json(
          { message: 'Custom error' },
          { status: 400 }
        )
      })
    )

    await expect(apiFetch('/test')).rejects.toThrow('Custom error')
  })
})

describe('apiGet', () => {
  it('constructs query parameters correctly', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.get('foo')).toBe('bar')
        expect(url.searchParams.get('baz')).toBe('123')
        return HttpResponse.json({ success: true })
      })
    )

    await apiGet('/test', { foo: 'bar', baz: 123 })
  })

  it('filters out undefined parameters', async () => {
    server.use(
      http.get('http://localhost:8000/api/test', ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.has('defined')).toBe(true)
        expect(url.searchParams.has('undefined')).toBe(false)
        return HttpResponse.json({ success: true })
      })
    )

    await apiGet('/test', { defined: 'value', undefined: undefined })
  })
})
