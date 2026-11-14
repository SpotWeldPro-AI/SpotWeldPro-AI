import { BrowserRouter, Routes, Route, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { useState, useEffect, lazy, Suspense } from 'react'
import { clearAuthStorage, currentUser, classifyMeError, pingBackend } from './api/client'
import type { UserResponse } from './api/client'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectsPage } from './pages/ProjectsPage'
const EngineeringPage = lazy(() => import('./pages/EngineeringPage').then(m => ({ default: m.EngineeringPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const FailureProbabilityPage = lazy(() => import('./pages/FailureProbabilityPage').then(m => ({ default: m.FailureProbabilityPage })))
const AnalysisPage = lazy(() => import('./pages/AnalysisPage').then(m => ({ default: m.AnalysisPage })))
const WeldPointWizard = lazy(() => import('./pages/WeldPointWizard').then(m => ({ default: m.WeldPointWizard })))
const ModelCatalogPage = lazy(() => import('./pages/ModelCatalogPage').then(m => ({ default: m.ModelCatalogPage })))
const StatisticalAnalysisPage = lazy(() => import('./pages/StatisticalAnalysisPage').then(m => ({ default: m.StatisticalAnalysisPage })))
const EnergyPage = lazy(() => import('./pages/EnergyPage').then(m => ({ default: m.EnergyPage })))
const HelpCenterPage = lazy(() => import('./pages/HelpCenterPage').then(m => ({ default: m.HelpCenterPage })))
const StaticInspectionPage = lazy(() => import('./pages/StaticInspectionPage').then(m => ({ default: m.StaticInspectionPage })))
const LiveMonitoringPage = lazy(() => import('./pages/LiveMonitoringPage').then(m => ({ default: m.LiveMonitoringPage })))
const AnnotationPage = lazy(() => import('./pages/AnnotationPage').then(m => ({ default: m.AnnotationPage })))
const DatasetDashboardPage = lazy(() => import('./pages/DatasetDashboardPage').then(m => ({ default: m.DatasetDashboardPage })))
const ConflictReviewPage = lazy(() => import('./pages/ConflictReviewPage').then(m => ({ default: m.ConflictReviewPage })))
const FeaturesPage = lazy(() => import('./pages/FeaturesPage').then(m => ({ default: m.FeaturesPage })))
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage').then(m => ({ default: m.HowItWorksPage })))
const PackagesPage = lazy(() => import('./pages/PackagesPage').then(m => ({ default: m.PackagesPage })))
const DemoPage = lazy(() => import('./pages/DemoPage').then(m => ({ default: m.DemoPage })))
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })))
import { AppLanguageContext, getInitialAppLang, persistAppLang } from './i18n/AppLanguageContext'
import { WeldAnalysisProvider } from './context/WeldAnalysisContext'
import { useAppLanguage } from './i18n/useAppLanguage'
import { LangContext, getInitialLang, persistLang } from './i18n/useLang'
import type { AppLanguage } from './i18n/appContent'
import type { Lang } from './i18n/publicContent'
import type { Project } from './types/project'
import './styles.css'

/* Public pre-login design system — global stylesheet injected once at root.
   Short lines only to keep the file writer stable. */
type Page = 'dashboard' | 'projects' | 'analysis' | 'engineering' | 'failure' | 'models' | 'statistical' | 'energy' | 'help' | 'inspection' | 'live' | 'annotation' | 'dataset_dashboard' | 'conflict_review'

type NavItem = { id: Page; label: string; mk: string }
type NavGroup = { id: string; label: string; accordion: boolean; items: NavItem[] }

/** Static nav structure — internal IDs are stable, labels are translated at render time. */
const NAV: NavGroup[] = [
  {
    id: 'dash', label: 'Dashboard', accordion: false,
    items: [{ id: 'dashboard', label: 'Dashboard', mk: 'D' }],
  },
  {
    id: 'work', label: 'WORK', accordion: true,
    items: [
      { id: 'projects', label: 'Projects & Weld Points', mk: 'P' },
      { id: 'engineering', label: 'Weld Lobe Lab', mk: 'L' },
    ],
  },
  {
    id: 'analysis', label: 'ANALYSIS', accordion: true,
    items: [
      { id: 'analysis', label: 'Weld Quality Analysis', mk: 'Q' },
      { id: 'failure', label: 'Failure Analysis', mk: 'F' },
    ],
  },
  {
    id: 'models_group', label: 'MODELS', accordion: false,
    items: [{ id: 'models', label: 'Model Catalog', mk: 'M' }],
  },
  {
    id: 'stats', label: 'STATISTICS', accordion: false,
    items: [{ id: 'statistical', label: 'Taguchi DOE & ANOVA', mk: 'S' }],
  },
  {
    id: 'energy_group', label: 'ENERGY', accordion: false,
    items: [{ id: 'energy', label: 'Energy Intelligence', mk: 'E' }],
  },
  {
    id: 'vision_group', label: 'VISION', accordion: true,
    items: [
      { id: 'inspection', label: 'Static Inspection', mk: 'I' },
      { id: 'live', label: 'Live Monitoring', mk: 'V' },
      { id: 'annotation', label: 'Annotation', mk: 'A' },
      { id: 'dataset_dashboard', label: 'Dataset Dashboard', mk: 'DD' },
      { id: 'conflict_review', label: 'Conflict Review', mk: 'CR' },
    ],
  },
  {
    id: 'help_group', label: 'HELP', accordion: false,
    items: [{ id: 'help', label: 'Help Center', mk: 'H' }],
  },
]

function Sidebar({
  page, setPage, collapsed, setCollapsed, mobileOpen, setMobileOpen,
}: {
  page: Page
  setPage: (p: Page) => void
  collapsed: boolean
  setCollapsed: (v: boolean) => void
  mobileOpen: boolean
  setMobileOpen: (v: boolean) => void
}) {
  const { t } = useAppLanguage()

  const [open, setOpen] = useState<Record<string, boolean>>(() => {
    try { const s = localStorage.getItem('sb_open'); return s ? JSON.parse(s) : {} } catch { return {} }
  })

  useEffect(() => {
    const gid = NAV.find((g) => g.accordion && g.items.some((i) => i.id === page))?.id
    if (gid) {
      setOpen((prev) => {
        if (prev[gid]) return prev
        const next = { ...prev, [gid]: true }
        try { localStorage.setItem('sb_open', JSON.stringify(next)) } catch { /**/ }
        return next
      })
    }
  }, [page])

  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMobileOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileOpen, setMobileOpen])

  function toggleGroup(id: string) {
    setOpen((prev) => {
      const next = { ...prev, [id]: !prev[id] }
      try { localStorage.setItem('sb_open', JSON.stringify(next)) } catch { /**/ }
      return next
    })
  }

  function handleNav(id: Page) {
    setPage(id)
    setMobileOpen(false)
  }

  function toggleCollapsed() {
    const next = !collapsed
    setCollapsed(next)
    try { localStorage.setItem('sb_collapsed', String(next)) } catch { /**/ }
  }

  const iconOnly = collapsed && !mobileOpen

  return (
    <>
      {mobileOpen && (
        <div className="sb-backdrop" aria-hidden="true" onClick={() => setMobileOpen(false)} />
      )}
      <aside className={'sidebar' + (mobileOpen ? ' sb-mobile-open' : '')} aria-label="Primary navigation">
        <div className="sidebar-brand">
          {iconOnly ? (
            <div className="sidebar-logo-icon-wrap">
              <img src="/spotweldpro-logo.png" alt="SpotWeldPro AI" />
            </div>
          ) : (
            <img
              src="/spotweldpro-logo.png"
              alt="SpotWeldPro AI"
              className="sidebar-logo"
            />
          )}
        </div>
        <nav className="sidebar-nav">
          {iconOnly ? (
            NAV.flatMap((g) => g.items).map((item) => (
              <button
                key={item.id}
                className={'nav-item' + (page === item.id ? ' active' : '')}
                aria-current={page === item.id ? 'page' : undefined}
                onClick={() => handleNav(item.id)}
                title={t.nav.items[item.id] ?? item.label}
              >
                <span className="nav-mk" aria-hidden="true">{item.mk}</span>
              </button>
            ))
          ) : (
            NAV.map((group) => {
              if (!group.accordion) {
                const item = group.items[0]
                return (
                  <button
                    key={item.id}
                    className={'nav-item' + (page === item.id ? ' active' : '')}
                    aria-current={page === item.id ? 'page' : undefined}
                    onClick={() => handleNav(item.id)}
                  >
                    <span className="nav-mk" aria-hidden="true">{item.mk}</span>
                    <span className="nav-label">{t.nav.items[item.id] ?? item.label}</span>
                  </button>
                )
              }
              const isOpen = !!open[group.id]
              const panelId = 'sbp-' + group.id
              return (
                <div key={group.id} className="sb-group">
                  <button
                    className="sb-group-hd"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => toggleGroup(group.id)}
                  >
                    <span className="sb-group-label">{t.nav.groups[group.id] ?? group.label}</span>
                    <span className="sb-chevron" aria-hidden="true">{isOpen ? '▴' : '▾'}</span>
                  </button>
                  {isOpen && (
                    <div id={panelId} role="group">
                      {group.items.map((item) => (
                        <button
                          key={item.id}
                          className={'nav-item' + (page === item.id ? ' active' : '')}
                          aria-current={page === item.id ? 'page' : undefined}
                          onClick={() => handleNav(item.id)}
                        >
                          <span className="nav-mk" aria-hidden="true">{item.mk}</span>
                          <span className="nav-label">{t.nav.items[item.id] ?? item.label}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </nav>
        <div className="sidebar-foot-wrap">
          <button
            className="sb-collapse-btn"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={toggleCollapsed}
          >
            <span aria-hidden="true">{collapsed ? '▶' : '◀'}</span>
          </button>
        </div>
      </aside>
    </>
  )
}

function Topbar({ page, userName, onSignOut, onHamburger }: { page: Page; userName: string; onSignOut: () => void; onHamburger: () => void }) {
  const { lang, setLang, t } = useAppLanguage()
  const item = NAV.flatMap((g) => g.items).find((i) => i.id === page)
  const group = NAV.find((g) => g.items.some((i) => i.id === page))
  const title = t.nav.items[page] ?? item?.label ?? 'SpotWeldPro'
  const groupLabel = group ? (t.nav.groups[group.id] ?? group.label) : 'SpotWeldPro'
  const initials = userName.trim() ? userName.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() : '…'

  function handleLang(next: AppLanguage) {
    persistAppLang(next)
    setLang(next)
  }

  return (
    <header className="topbar">
      <div className="topbar-start">
        <button className="hamburger-btn" aria-label="Open navigation" onClick={onHamburger}>
          <span aria-hidden="true">☰</span>
        </button>
        <div className="topbar-module">
          <span className="topbar-title">{title}</span>
          <span className="topbar-crumb">SpotWeldPro AI / {groupLabel}</span>
        </div>
      </div>
      <div className="topbar-user">
        <div className="lang-switch" role="group" aria-label="Language">
          {(['tr', 'en'] as AppLanguage[]).map((l) => (
            <button
              key={l}
              type="button"
              className={'lang-btn' + (lang === l ? ' lang-btn-active' : '')}
              aria-pressed={lang === l}
              onClick={() => handleLang(l)}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <span className="user-chip"><span className="user-avatar" aria-hidden="true">{initials}</span>{userName}</span>
        <button className="signout-btn" onClick={onSignOut}>
          {t.topbar.signOut}
        </button>
      </div>
    </header>
  )
}

/* AUTH-UX-04-R3A: 5-state authenticated shell.
   checking → calls GET /auth/me; authenticated → renders app;
   unauthenticated → redirects /login; retryable → network/5xx, tokens preserved;
   error → 403/422/other, tokens preserved. */
type AuthState = 'checking' | 'authenticated' | 'unauthenticated' | 'retryable' | 'error'

function AuthenticatedApp() {
  const [authState, setAuthState] = useState<AuthState>(() =>
    localStorage.getItem('access_token') ? 'checking' : 'unauthenticated'
  )
  const [page, setPage] = useState<Page>('dashboard')
  const [project, setProject] = useState<Project | null>(null)
  const [userName, setUserName] = useState('')
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sb_collapsed') === 'true' } catch { return false }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const [lang, setLang] = useState<AppLanguage>(getInitialAppLang)
  const navigate = useNavigate()

  const [pingAttempt, setPingAttempt] = useState(0)

  // Session check with cold-start recovery: ping backend first (up to 6 attempts, ~90 s),
  // then validate the token. AbortController cancels in-flight work on unmount or manual retry.
  useEffect(() => {
    if (authState !== 'checking') return
    let cancelled = false
    const controller = new AbortController()
    setPingAttempt(0)

    async function run() {
      const pingResult = await pingBackend(
        6,
        (attempt) => { if (!cancelled) setPingAttempt(attempt) },
        undefined,
        undefined,
        controller.signal,
      )
      if (cancelled) return
      if (pingResult !== 'ok') {
        setAuthState('retryable')
        return
      }
      try {
        const user = await currentUser()
        if (cancelled) return
        setUserName(user.full_name || user.username || user.email)
        setAuthState('authenticated')
      } catch (err: unknown) {
        if (cancelled) return
        const kind = classifyMeError(err)
        if (kind === 'unauthorized') {
          clearAuthStorage()
          setAuthState('unauthenticated')
        } else if (kind === 'retryable') {
          setAuthState('retryable')
        } else {
          setAuthState('error')
        }
      }
    }

    run()
    return () => { cancelled = true; controller.abort() }
  }, [authState])

  // Retry automatically when the tab becomes visible after a retryable failure.
  useEffect(() => {
    if (authState !== 'retryable') return
    const onVisible = () => {
      if (document.visibilityState === 'visible') setAuthState('checking')
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [authState])

  if (authState === 'unauthenticated') return <Navigate to="/login" replace />
  if (authState === 'checking') return (
    <div className="auth-screen">
      <div className="spinner" aria-hidden="true" />
      <span>{pingAttempt === 0 ? 'Validating session…' : `Backend starting up — attempt ${pingAttempt + 1} of 6…`}</span>
    </div>
  )
  if (authState === 'retryable') return (
    <div className="auth-screen">
      <span>Backend unavailable. Check connection and retry.</span>
      <button className="btn btn-primary" onClick={() => setAuthState('checking')}>Retry</button>
    </div>
  )
  if (authState === 'error') return (
    <div className="auth-screen">
      <span>Session error. Please return to login.</span>
      <button className="btn btn-primary" onClick={() => setAuthState('checking')}>Retry</button>
      <button className="btn btn-secondary" onClick={() => navigate('/login')}>Go to login</button>
    </div>
  )

  if (project) return (
    <Suspense fallback={<div className="auth-screen"><div className="spinner" aria-hidden="true" /></div>}>
      <WeldPointWizard project={project} onBack={() => setProject(null)} />
    </Suspense>
  )

  return (
    <AppLanguageContext.Provider value={{ lang, setLang }}>
      <div className={'app-shell' + (collapsed ? ' shell-collapsed' : '')}>
        <Topbar
          page={page}
          userName={userName || '…'}
          onSignOut={() => {
            clearAuthStorage()
            navigate('/login')
          }}
          onHamburger={() => setMobileOpen(true)}
        />
        <Sidebar
          page={page} setPage={setPage}
          collapsed={collapsed} setCollapsed={setCollapsed}
          mobileOpen={mobileOpen} setMobileOpen={setMobileOpen}
        />
        <main className="main">
          <WeldAnalysisProvider>
            <Suspense fallback={<div className="state-msg"><div className="spinner" aria-hidden="true" /></div>}>
              {page === 'dashboard' && <DashboardPage />}
              {page === 'projects' && <ProjectsPage onOpen={setProject} />}
              {page === 'analysis' && <AnalysisPage />}
              {page === 'engineering' && <EngineeringPage />}
              {page === 'failure' && <FailureProbabilityPage onNavigateToAnalysis={() => setPage('analysis')} />}
              {page === 'models' && <ModelCatalogPage />}
              {page === 'statistical' && <StatisticalAnalysisPage />}
              {page === 'energy' && <EnergyPage />}
              {page === 'inspection' && <StaticInspectionPage />}
              {page === 'live' && <LiveMonitoringPage />}
              {page === 'annotation' && <AnnotationPage />}
              {page === 'dataset_dashboard' && <DatasetDashboardPage />}
              {page === 'conflict_review' && <ConflictReviewPage />}
              {page === 'help' && <HelpCenterPage />}
            </Suspense>
          </WeldAnalysisProvider>
        </main>
      </div>
    </AppLanguageContext.Provider>
  )
}

/* Public /login route — demo credentials only, frontend mock session. */
function PublicLogin() {
  const navigate = useNavigate()
  return (
    <LoginPage
      onLogin={() => {
        navigate('/app')
      }}
    />
  )
}

/**
 * PUBLIC-I18N-01-HF2: Single source of truth for public language state.
 * Owns useState<Lang>, reads localStorage via getInitialLang(), writes via
 * persistLang(). Renders LangContext.Provider so every descendant — both the
 * page component AND its <PublicLayout> child — reads from the same reactive
 * context value.  PublicLayout is now a pure consumer (useLang() only).
 *
 * Uses React Router's layout-route / Outlet pattern so the Provider is NOT
 * remounted on navigation between public routes — lang state survives
 * cross-route navigation, fulfilling the route persistence requirement.
 */
function PublicLangProvider() {
  const [lang, setLangState] = useState<Lang>(getInitialLang)

  function setLang(next: Lang) {
    persistLang(next)
    setLangState(next)
  }

  return (
    <LangContext.Provider value={{ lang, setLang }}>
      <Suspense fallback={<div className="auth-screen"><div className="spinner" aria-hidden="true" /></div>}>
        <Outlet />
      </Suspense>
    </LangContext.Provider>
  )
}

/* AUTH-UX-04-R3A: Synchronous fast-path root redirect.
   No network call — token presence only. Actual validation happens in AuthenticatedApp. */
function RootRedirect() {
  const hasToken = Boolean(localStorage.getItem('access_token'))
  return <Navigate to={hasToken ? '/app' : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLangProvider />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/features" element={<FeaturesPage />} />
          <Route path="/how-it-works" element={<HowItWorksPage />} />
          <Route path="/packages" element={<PackagesPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/login" element={<PublicLogin />} />
        </Route>
        <Route path="/app" element={<AuthenticatedApp />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
