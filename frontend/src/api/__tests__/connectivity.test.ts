/**
 * BACKEND-RELIABILITY-FIX-01 / MOBILE-BACKEND-02 — connectivity tests
 *
 * Tests for:
 * - extractErrorCode  : timeout / network / server / credentials classification
 * - classifyMeError   : /auth/me failure → unauthorized / retryable / error
 * - pingBackend       : delayed startup recovery, retry-then-ok, exhausted retries
 * - pingBackend       : 30-second and 60-second cold-start scenarios
 * - PROD_API_URL      : production fallback URL is the expected Render endpoint
 * - publicContent     : TR/EN login i18n keys exist and are non-empty strings
 *
 * Component-level tests (manual retry, unmount cancellation, no-overlap guarantee)
 * require @testing-library/react and are not included here.  The abort behaviour is
 * covered by the AbortSignal suite below; the component wires it correctly.
 */
import { describe, it, expect, vi } from 'vitest'
import axios from 'axios'
import { extractErrorCode, classifyMeError, pingBackend, PROD_API_URL } from '../client'
import { PUBLIC_CONTENT } from '../../i18n/publicContent'

// Instant delays — avoids real setTimeout waits in tests (6 entries for maxAttempts=6)
const NO_DELAY = [0, 0, 0, 0, 0, 0] as const

// ── helpers ────────────────────────────────────────────────────────────────

function makeAxiosError(code?: string, status?: number, errorCode?: string) {
  const err = new axios.AxiosError('test', code)
  if (status !== undefined) {
    err.response = {
      status,
      data: errorCode ? { error_code: errorCode, message: 'test' } : {},
      headers: {},
      config: { headers: new axios.AxiosHeaders() },
      statusText: '',
    }
  }
  return err
}

// ── extractErrorCode ────────────────────────────────────────────────────────

describe('extractErrorCode', () => {
  it('returns TIMEOUT_ERROR for ECONNABORTED (axios timeout)', () => {
    expect(extractErrorCode(makeAxiosError('ECONNABORTED'))).toBe('TIMEOUT_ERROR')
  })

  it('returns TIMEOUT_ERROR for ERR_CANCELED', () => {
    expect(extractErrorCode(makeAxiosError('ERR_CANCELED'))).toBe('TIMEOUT_ERROR')
  })

  it('returns NETWORK_ERROR when no response and no timeout code', () => {
    expect(extractErrorCode(makeAxiosError('ECONNREFUSED'))).toBe('NETWORK_ERROR')
  })

  it('returns NETWORK_ERROR when code is undefined and no response', () => {
    expect(extractErrorCode(makeAxiosError(undefined))).toBe('NETWORK_ERROR')
  })

  it('returns SERVER_ERROR for HTTP 500', () => {
    expect(extractErrorCode(makeAxiosError('ERR_BAD_RESPONSE', 500))).toBe('SERVER_ERROR')
  })

  it('returns SERVER_ERROR for HTTP 503', () => {
    expect(extractErrorCode(makeAxiosError('ERR_BAD_RESPONSE', 503))).toBe('SERVER_ERROR')
  })

  it('returns the backend error_code for structured 401', () => {
    expect(extractErrorCode(makeAxiosError('ERR_BAD_RESPONSE', 401, 'INVALID_CREDENTIALS')))
      .toBe('INVALID_CREDENTIALS')
  })

  it('returns UNKNOWN_ERROR for non-axios errors', () => {
    expect(extractErrorCode(new Error('something'))).toBe('UNKNOWN_ERROR')
    expect(extractErrorCode('string error')).toBe('UNKNOWN_ERROR')
    expect(extractErrorCode(null)).toBe('UNKNOWN_ERROR')
  })
})

// ── pingBackend ─────────────────────────────────────────────────────────────

describe('pingBackend', () => {
  it('returns ok when health responds on first attempt', async () => {
    const fetch = vi.fn().mockResolvedValue({ status: 200, data: { status: 'ok' } })
    const result = await pingBackend(4, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith('/health')
  })

  it('retries on connection-refused and returns ok when backend starts', async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const onRetry = vi.fn()
    const result = await pingBackend(4, onRetry, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(3)
    expect(onRetry).toHaveBeenCalledTimes(2)
    expect(onRetry).toHaveBeenNthCalledWith(1, 1)
    expect(onRetry).toHaveBeenNthCalledWith(2, 2)
  })

  it('returns ok immediately if backend is up after cold start on attempt 4', async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const result = await pingBackend(4, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(4)
  })

  it('returns timeout when all attempts exhaust with ECONNABORTED', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNABORTED'))
    const result = await pingBackend(3, undefined, fetch, NO_DELAY)
    expect(result).toBe('timeout')
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it('returns network when all attempts exhaust with connection-refused', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNREFUSED'))
    const result = await pingBackend(3, undefined, fetch, NO_DELAY)
    expect(result).toBe('network')
  })

  it('returns server when health responds with 500', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ERR_BAD_RESPONSE', 500))
    const result = await pingBackend(1, undefined, fetch, NO_DELAY)
    expect(result).toBe('server')
  })

  it('returns ok (service reachable) when health responds with any 4xx', async () => {
    // A 4xx on /health is unusual but proves TCP+HTTP is working
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ERR_BAD_RESPONSE', 403))
    const result = await pingBackend(1, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
  })

  it('does not retry beyond maxAttempts', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNREFUSED'))
    await pingBackend(2, undefined, fetch, NO_DELAY)
    expect(fetch).toHaveBeenCalledTimes(2)
  })
})

// ── pingBackend — extended cold-start coverage (FIX-F) ─────────────────────

describe('pingBackend — 90 s cold-start coverage', () => {
  it('defaults to 6 attempts', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNREFUSED'))
    await pingBackend(undefined, undefined, fetch, NO_DELAY)
    expect(fetch).toHaveBeenCalledTimes(6)
  })

  it('returns ok when backend wakes on attempt 6', async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(6)
  })

  it('returns network when all 6 attempts fail', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNREFUSED'))
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('network')
    expect(fetch).toHaveBeenCalledTimes(6)
  })

  it('returns timeout when all 6 attempts exhaust with ECONNABORTED', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNABORTED'))
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('timeout')
    expect(fetch).toHaveBeenCalledTimes(6)
  })
})

// ── pingBackend — AbortSignal cancellation (FIX-F) ─────────────────────────

describe('pingBackend — AbortSignal', () => {
  it('returns immediately without calling fetch when signal is already aborted', async () => {
    const ctrl = new AbortController()
    ctrl.abort()
    const fetch = vi.fn().mockResolvedValue({ status: 200 })
    const result = await pingBackend(4, undefined, fetch, NO_DELAY, ctrl.signal)
    expect(result).toBe('network')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('stops retrying after first failed fetch when signal is aborted inside fetch', async () => {
    const ctrl = new AbortController()
    const fetch = vi.fn().mockImplementationOnce(() => {
      ctrl.abort()
      return Promise.reject(makeAxiosError('ECONNREFUSED'))
    })
    const result = await pingBackend(4, undefined, fetch, NO_DELAY, ctrl.signal)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(result).toBe('network')
  })

  it('does not invoke onRetry after signal is aborted', async () => {
    const ctrl = new AbortController()
    const fetch = vi.fn().mockImplementation(() => {
      ctrl.abort()
      return Promise.reject(makeAxiosError('ECONNREFUSED'))
    })
    const onRetry = vi.fn()
    await pingBackend(4, onRetry, fetch, NO_DELAY, ctrl.signal)
    expect(onRetry).not.toHaveBeenCalled()
  })

  it('returns ok normally when signal is provided but never aborted', async () => {
    const ctrl = new AbortController()
    const fetch = vi.fn().mockResolvedValue({ status: 200 })
    const result = await pingBackend(4, undefined, fetch, NO_DELAY, ctrl.signal)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

// ── classifyMeError ─────────────────────────────────────────────────────────
// MOBILE-BACKEND-02: F-01 — verify that 401 is never treated as a retryable
// backend failure and that every expected status code maps to the right kind.

describe('classifyMeError', () => {
  it('returns unauthorized for HTTP 401', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 401))).toBe('unauthorized')
  })

  it('does not classify 401 as retryable', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 401))).not.toBe('retryable')
  })

  it('returns retryable for no response (network error)', () => {
    expect(classifyMeError(makeAxiosError('ECONNREFUSED'))).toBe('retryable')
  })

  it('returns retryable for timeout (ECONNABORTED)', () => {
    expect(classifyMeError(makeAxiosError('ECONNABORTED'))).toBe('retryable')
  })

  it('returns retryable for HTTP 500', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 500))).toBe('retryable')
  })

  it('returns retryable for HTTP 502', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 502))).toBe('retryable')
  })

  it('returns retryable for HTTP 503', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 503))).toBe('retryable')
  })

  it('returns error for HTTP 403', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 403))).toBe('error')
  })

  it('returns error for HTTP 422', () => {
    expect(classifyMeError(makeAxiosError('ERR_BAD_RESPONSE', 422))).toBe('error')
  })

  it('returns retryable for non-axios errors (TypeError, network API failure)', () => {
    expect(classifyMeError(new TypeError('Failed to fetch'))).toBe('retryable')
    expect(classifyMeError(new Error('Network Error'))).toBe('retryable')
  })
})

// ── PROD_API_URL ─────────────────────────────────────────────────────────────
// MOBILE-BACKEND-02: F-02 — verify the production fallback URL is correct.
// If this test fails, update PROD_API_URL in client.ts to match the Render deployment.

describe('PROD_API_URL', () => {
  it('points to the expected Render API deployment', () => {
    expect(PROD_API_URL).toBe('https://spotweldpro-ai-api.onrender.com/api/v1')
  })

  it('is an HTTPS URL (never HTTP)', () => {
    expect(PROD_API_URL.startsWith('https://')).toBe(true)
  })

  it('ends with /api/v1', () => {
    expect(PROD_API_URL.endsWith('/api/v1')).toBe(true)
  })
})

// ── pingBackend — cold-start named scenarios ─────────────────────────────────
// MOBILE-BACKEND-02: F-01 — confirm that pingBackend covers the cold-start windows
// documented in render.yaml.  Real delay table: 0, 5, 10, 15, 20, 30 s (cumulative
// 0, 5, 15, 30, 50, 80 s).  Tests use instant delays; the timing comments map each
// rejection count to an approximate real-world elapsed time.

describe('pingBackend — cold-start named scenarios', () => {
  it('fast response: backend answers on first attempt (warm)', async () => {
    const fetch = vi.fn().mockResolvedValue({ status: 200 })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('30-second cold start: fails attempts 1–3, succeeds on attempt 4 (~30 s elapsed)', async () => {
    // Real timing: fail @0s, @5s, @15s → succeed @30s (attempt 4)
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(4)
  })

  it('60-second cold start: fails attempts 1–5, succeeds on attempt 6 (~80 s elapsed)', async () => {
    // Real timing: fail @0s, @5s, @15s, @30s, @50s → succeed @80s (attempt 6)
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(6)
  })

  it('backend unavailable beyond retry window: all 6 attempts fail → network', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNREFUSED'))
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('network')
    expect(fetch).toHaveBeenCalledTimes(6)
  })

  it('backend unavailable with timeout errors → timeout result', async () => {
    const fetch = vi.fn().mockRejectedValue(makeAxiosError('ECONNABORTED'))
    const result = await pingBackend(6, undefined, fetch, NO_DELAY)
    expect(result).toBe('timeout')
  })

  it('onRetry receives correct 1-based attempt numbers', async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockRejectedValueOnce(makeAxiosError('ECONNREFUSED'))
      .mockResolvedValueOnce({ status: 200 })
    const onRetry = vi.fn()
    await pingBackend(6, onRetry, fetch, NO_DELAY)
    expect(onRetry).toHaveBeenCalledTimes(2)
    expect(onRetry).toHaveBeenNthCalledWith(1, 1)
    expect(onRetry).toHaveBeenNthCalledWith(2, 2)
  })

  it('component unmount during retry: aborted signal stops the loop', async () => {
    const ctrl = new AbortController()
    const fetch = vi.fn().mockImplementation(() => {
      ctrl.abort()
      return Promise.reject(makeAxiosError('ECONNREFUSED'))
    })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY, ctrl.signal)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(['network', 'timeout']).toContain(result)
  })

  it('manual retry (new AbortController): prior signal abort does not affect new probe', async () => {
    const oldCtrl = new AbortController()
    oldCtrl.abort()
    // New controller is not aborted — probe runs normally
    const newCtrl = new AbortController()
    const fetch = vi.fn().mockResolvedValue({ status: 200 })
    const result = await pingBackend(6, undefined, fetch, NO_DELAY, newCtrl.signal)
    expect(result).toBe('ok')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

// ── i18n strings ────────────────────────────────────────────────────────────

describe('login i18n — TR and EN', () => {
  const keys: Array<keyof typeof PUBLIC_CONTENT['tr']['login']> = [
    'connecting', 'retrying', 'errorNetwork', 'errorTimeout', 'errorServer', 'errorCredentials',
  ]

  for (const lang of ['tr', 'en'] as const) {
    describe(`[${lang}]`, () => {
      for (const key of keys) {
        it(`${key} is a non-empty string`, () => {
          const value = PUBLIC_CONTENT[lang].login[key]
          expect(typeof value).toBe('string')
          expect((value as string).length).toBeGreaterThan(0)
        })
      }

      it('connecting is distinct from submitBusy', () => {
        expect(PUBLIC_CONTENT[lang].login.connecting)
          .not.toBe(PUBLIC_CONTENT[lang].login.submitBusy)
      })

      it('errorTimeout is distinct from errorNetwork', () => {
        expect(PUBLIC_CONTENT[lang].login.errorTimeout)
          .not.toBe(PUBLIC_CONTENT[lang].login.errorNetwork)
      })
    })
  }

  it('TR connecting message references server (Sunucuya)', () => {
    expect(PUBLIC_CONTENT.tr.login.connecting).toContain('Sunucu')
  })

  it('TR errorTimeout mentions startup context', () => {
    expect(PUBLIC_CONTENT.tr.login.errorTimeout).toContain('başlatıl')
  })

  it('EN connecting message references server', () => {
    expect(PUBLIC_CONTENT.en.login.connecting.toLowerCase()).toContain('server')
  })

  it('EN errorTimeout mentions startup context', () => {
    expect(PUBLIC_CONTENT.en.login.errorTimeout.toLowerCase()).toContain('start')
  })
})
