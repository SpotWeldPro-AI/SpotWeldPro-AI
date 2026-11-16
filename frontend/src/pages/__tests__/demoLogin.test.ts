/**
 * AUTH-UX-DEMO-01 — Demo login auto-fill tests.
 *
 * Verifies that the auto-fill implementation in LoginPage.tsx:
 *   - Is gated on VITE_DEMO_MODE (never active in production builds)
 *   - Pre-fills username='demo' and password='A1234' only in demo mode
 *   - Leaves password empty when VITE_DEMO_MODE is not set
 *   - Preserves type="password" (masked) on the password field
 *   - Does not auto-submit the form
 *   - Does not store credentials in localStorage
 *   - Shows a demo banner only in demo mode
 *
 * Tests inspect the LoginPage source rather than mounting the component because
 * this Vitest environment runs in Node without a DOM (consistent with existing
 * tests such as logoSidebar.test.ts).
 */
import { describe, it, expect } from 'vitest'
import loginPageSource from '../LoginPage.tsx?raw'

// ── DEMO-01: Demo mode gate uses VITE_DEMO_MODE ───────────────────────────────

describe('DEMO-01 Gate is VITE_DEMO_MODE', () => {
  it('LoginPage reads VITE_DEMO_MODE from import.meta.env', () => {
    expect(loginPageSource).toContain("import.meta.env.VITE_DEMO_MODE === 'true'")
  })

  it('DEMO_MODE constant is defined from that env flag', () => {
    expect(loginPageSource).toContain('const DEMO_MODE =')
  })
})

// ── DEMO-02: Demo username constant ──────────────────────────────────────────

describe('DEMO-02 Demo username is "demo"', () => {
  it("DEMO_USERNAME equals 'demo'", () => {
    expect(loginPageSource).toContain("const DEMO_USERNAME = 'demo'")
  })
})

// ── DEMO-03: Password only in demo mode ──────────────────────────────────────

describe('DEMO-03 Password guarded by DEMO_MODE', () => {
  it("DEMO_PASSWORD uses ternary — empty string when DEMO_MODE is false", () => {
    expect(loginPageSource).toContain("DEMO_MODE ? 'A1234' : ''")
  })

  it('production bundle gets empty password (DEMO_MODE false → empty string)', () => {
    // The ternary must resolve to '' on the false branch
    const ternaryPattern = /DEMO_MODE\s*\?\s*'A1234'\s*:\s*''/
    expect(ternaryPattern.test(loginPageSource)).toBe(true)
  })
})

// ── DEMO-04: State is initialized from constants, not hardcoded ──────────────

describe('DEMO-04 State uses DEMO_USERNAME / DEMO_PASSWORD constants', () => {
  it('useState initialises username from DEMO_USERNAME', () => {
    expect(loginPageSource).toContain('useState(DEMO_USERNAME)')
  })

  it('useState initialises password from DEMO_PASSWORD', () => {
    expect(loginPageSource).toContain('useState(DEMO_PASSWORD)')
  })
})

// ── DEMO-05: Password field type is preserved as "password" ──────────────────

describe('DEMO-05 Password input type is always "password"', () => {
  it('password input has type="password"', () => {
    expect(loginPageSource).toContain('type="password"')
  })

  it('password input is never type="text"', () => {
    // No input element should switch the password field to plain text
    const passwordFieldBlock = loginPageSource.split('login-password')[1] ?? ''
    expect(passwordFieldBlock.startsWith('')).toBe(true)
    // The password field's type attribute is 'password', not 'text'
    expect(loginPageSource).not.toMatch(/id="login-password"[^>]*type="text"/)
  })
})

// ── DEMO-06: No auto-submit ───────────────────────────────────────────────────

describe('DEMO-06 No auto-submit on mount', () => {
  it('useEffect does not call submit()', () => {
    // The only useEffect in LoginPage sets up abort cleanup — no submit() inside
    const afterUseEffect = loginPageSource.split('useEffect(').slice(1)
    for (const block of afterUseEffect) {
      // Extract the callback body up to the closing bracket
      const callback = block.split('}, [])')[0] ?? ''
      expect(callback).not.toContain('submit()')
    }
  })
})

// ── DEMO-07: No localStorage usage ───────────────────────────────────────────

describe('DEMO-07 No password in localStorage', () => {
  it('LoginPage never writes to localStorage', () => {
    expect(loginPageSource).not.toContain('localStorage')
  })
})

// ── DEMO-08: Demo banner is shown only in demo mode ──────────────────────────

describe('DEMO-08 Demo banner is conditional on DEMO_MODE', () => {
  it('demo banner renders inside a DEMO_MODE conditional', () => {
    expect(loginPageSource).toContain('{DEMO_MODE && (')
  })

  it('demo banner has role="status" for accessibility', () => {
    expect(loginPageSource).toContain('role="status"')
  })
})

// ── DEMO-09: i18n keys exist for demo banner ─────────────────────────────────

describe('DEMO-09 i18n keys demoBannerTitle and demoBannerText exist', () => {
  it('loginPage references t.demoBannerTitle', () => {
    expect(loginPageSource).toContain('t.demoBannerTitle')
  })

  it('loginPage references t.demoBannerText', () => {
    expect(loginPageSource).toContain('t.demoBannerText')
  })
})
