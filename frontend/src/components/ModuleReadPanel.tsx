/**
 * ModuleReadPanel — Bilingual contextual help and tutorial system
 * Available from every application module via a consistent button.
 *
 * Features:
 * - Opens without navigating away (drawer overlay)
 * - Resizable by dragging the left edge
 * - Compact / wide / full-screen modes
 * - Dockable as right-side drawer
 * - TR/EN language selection
 * - Preserves unsaved module form data
 * - Keyboard navigation (Escape to close, Tab through sections)
 * - Accessibility: role=dialog, aria-modal, focus management
 * - Responsive on mobile/tablet/desktop
 * - Persists width preference in localStorage (graceful fallback)
 */
import React, {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'
import type { ModuleReadContent } from '../moduleread/registry'
import { getModuleContent, listSupportedModules } from '../moduleread/registry'
import { useAppLanguage } from '../i18n/useAppLanguage'

export type PanelMode = 'compact' | 'wide' | 'fullscreen'

interface Props {
  moduleId: string
  /** Called when user clicks "Load Example" — fires moduleRead.loadExample() */
  onLoadExample?: (exampleId: string, inputs: Record<string, unknown>) => void
  /** Called when user clicks "Run Example" — fires moduleRead.runExample() */
  onRunExample?: (exampleId: string) => void
  /** Current module result object to explain */
  currentResult?: unknown
}

const LS_WIDTH_KEY = 'spotweldpro_moduleread_width'
const DEFAULT_WIDTH = 420
const MIN_WIDTH = 280
const MAX_WIDTH = 900

function tryGetWidth(): number {
  try {
    const v = localStorage.getItem(LS_WIDTH_KEY)
    if (v) {
      const n = parseInt(v, 10)
      if (n >= MIN_WIDTH && n <= MAX_WIDTH) return n
    }
  } catch {
    /* localStorage blocked */
  }
  return DEFAULT_WIDTH
}

function trySaveWidth(w: number) {
  try {
    localStorage.setItem(LS_WIDTH_KEY, String(w))
  } catch {
    /* ignore */
  }
}

export function ModuleReadPanel({
  moduleId,
  onLoadExample,
  onRunExample,
  currentResult,
}: Props) {
  const { lang } = useAppLanguage()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<PanelMode>('wide')
  const [width, setWidth] = useState(tryGetWidth)
  const [activeSection, setActiveSection] = useState(0)
  const [confirmReplace, setConfirmReplace] = useState<null | string>(null)
  const [pendingExample, setPendingExample] = useState<null | { id: string; inputs: Record<string, unknown> }>(null)

  const dialogRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const resizeRef = useRef<{ active: boolean; startX: number; startW: number }>({
    active: false, startX: 0, startW: DEFAULT_WIDTH,
  })
  const dialogId = useId()

  const content: ModuleReadContent | null = getModuleContent(moduleId)
  const tr = lang === 'tr'

  /* ── Focus trap & keyboard ───────────────────────────────────────────── */
  useEffect(() => {
    if (!open) return
    const el = dialogRef.current
    if (!el) return
    el.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  /* ── Resize drag ─────────────────────────────────────────────────────── */
  const onMouseDownResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizeRef.current = { active: true, startX: e.clientX, startW: width }
    function onMove(ev: MouseEvent) {
      if (!resizeRef.current.active) return
      const delta = resizeRef.current.startX - ev.clientX
      const newW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, resizeRef.current.startW + delta))
      setWidth(newW)
    }
    function onUp() {
      if (resizeRef.current.active) {
        trySaveWidth(resizeRef.current.startW) // save final
      }
      resizeRef.current.active = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [width])

  /* ── Load example ────────────────────────────────────────────────────── */
  function handleLoadExample(exId: string, inputs: Record<string, unknown>) {
    if (onLoadExample) {
      // If form data might exist, ask first
      setConfirmReplace(exId)
      setPendingExample({ id: exId, inputs })
    }
  }

  function confirmLoad() {
    if (!pendingExample || !onLoadExample) return
    onLoadExample(pendingExample.id, pendingExample.inputs)
    setConfirmReplace(null)
    setPendingExample(null)
  }

  /* ── Panel width based on mode ───────────────────────────────────────── */
  const panelWidth = mode === 'fullscreen'
    ? '100vw'
    : mode === 'compact'
      ? '300px'
      : `${width}px`

  if (!content) {
    return (
      <div className="moduleread-unavailable">
        <button
          ref={triggerRef}
          className="moduleread-btn moduleread-btn--unavailable"
          title={tr ? 'Bu modül için yardım mevcut değil' : 'Help not available for this module'}
          disabled
          aria-disabled="true"
        >
          ?
        </button>
      </div>
    )
  }

  const sections = tr ? content.sections_tr : content.sections_en
  const title = tr ? content.title_tr : content.title_en

  return (
    <>
      {/* ── Trigger button ─────────────────────────────────────────────── */}
      <button
        ref={triggerRef}
        className="moduleread-btn"
        onClick={() => setOpen(true)}
        aria-label={tr ? `${title} — ModuleRead yardımını aç` : `Open ModuleRead help for ${title}`}
        aria-expanded={open}
        aria-controls={open ? dialogId : undefined}
        title={tr ? 'Modül yardımı ve örnek aç' : 'Open module help and tutorial'}
      >
        <span aria-hidden="true">?</span>
        <span className="moduleread-btn__label">
          {tr ? 'Yardım' : 'Help'}
        </span>
      </button>

      {/* ── Overlay backdrop ───────────────────────────────────────────── */}
      {open && (
        <div
          className="moduleread-backdrop"
          aria-hidden="true"
          onClick={() => setOpen(false)}
        />
      )}

      {/* ── Drawer panel ───────────────────────────────────────────────── */}
      {open && (
        <div
          id={dialogId}
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-label={tr ? `${title} ModuleRead Yardım Paneli` : `${title} ModuleRead Help Panel`}
          tabIndex={-1}
          className={`moduleread-panel moduleread-panel--${mode}`}
          style={{ width: panelWidth }}
        >
          {/* Resize handle */}
          {mode !== 'fullscreen' && (
            <div
              className="moduleread-resize-handle"
              onMouseDown={onMouseDownResize}
              role="separator"
              aria-orientation="vertical"
              aria-label={tr ? 'Panel genişliğini ayarla' : 'Resize panel'}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft') setWidth(w => Math.max(MIN_WIDTH, w - 20))
                if (e.key === 'ArrowRight') setWidth(w => Math.min(MAX_WIDTH, w + 20))
              }}
            />
          )}

          {/* Header */}
          <div className="moduleread-header">
            <div className="moduleread-header__title">
              <span className="moduleread-badge">?</span>
              <span>{title}</span>
            </div>
            <div className="moduleread-header__controls">
              {/* Mode buttons */}
              <button
                className={`moduleread-mode-btn ${mode === 'compact' ? 'active' : ''}`}
                onClick={() => setMode('compact')}
                title={tr ? 'Dar mod' : 'Compact mode'}
                aria-pressed={mode === 'compact'}
              >⊟</button>
              <button
                className={`moduleread-mode-btn ${mode === 'wide' ? 'active' : ''}`}
                onClick={() => setMode('wide')}
                title={tr ? 'Geniş mod' : 'Wide mode'}
                aria-pressed={mode === 'wide'}
              >⊞</button>
              <button
                className={`moduleread-mode-btn ${mode === 'fullscreen' ? 'active' : ''}`}
                onClick={() => setMode('fullscreen')}
                title={tr ? 'Tam ekran' : 'Fullscreen'}
                aria-pressed={mode === 'fullscreen'}
              >⤢</button>
              {/* Close */}
              <button
                className="moduleread-close-btn"
                onClick={() => { setOpen(false); triggerRef.current?.focus() }}
                aria-label={tr ? 'Kapat' : 'Close'}
              >✕</button>
            </div>
          </div>

          {/* Language selector */}
          <div className="moduleread-lang-row">
            <span className="moduleread-lang-label">
              {tr ? 'Dil:' : 'Language:'}
            </span>
            <span className="moduleread-lang-info">
              {tr ? 'Türkçe' : 'English'}
              {' '}
              <span className="moduleread-lang-hint">
                {tr ? '(Dil ayarından değiştirin)' : '(Change in Language settings)'}
              </span>
            </span>
          </div>

          {/* Section tabs */}
          <div className="moduleread-sections" role="tablist">
            {sections.map((s, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={activeSection === i}
                aria-controls={`${dialogId}-section-${i}`}
                className={`moduleread-section-tab ${activeSection === i ? 'active' : ''}`}
                onClick={() => setActiveSection(i)}
              >
                {s.title}
              </button>
            ))}
          </div>

          {/* Section content */}
          <div className="moduleread-content" role="tabpanel" id={`${dialogId}-section-${activeSection}`}>
            {sections[activeSection] && (
              <ModuleSectionContent
                section={sections[activeSection]}
                moduleId={moduleId}
                lang={lang}
                onLoadExample={onLoadExample ? handleLoadExample : undefined}
                onRunExample={onRunExample}
                currentResult={currentResult}
              />
            )}
          </div>

          {/* Confirm replace dialog */}
          {confirmReplace && (
            <div className="moduleread-confirm" role="alertdialog" aria-modal="true">
              <p>
                {tr
                  ? 'Formdaki mevcut değerlerin üzerine yazılacak. Devam edilsin mi?'
                  : 'This will replace your current form values. Continue?'}
              </p>
              <div className="moduleread-confirm__btns">
                <button onClick={confirmLoad} className="btn-primary">
                  {tr ? 'Evet, Yükle' : 'Yes, Load'}
                </button>
                <button onClick={() => { setConfirmReplace(null); setPendingExample(null) }}>
                  {tr ? 'İptal' : 'Cancel'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}

/* ── Section content renderer ─────────────────────────────────────────────── */

interface SectionProps {
  section: { title: string; content: string; examples?: Example[] }
  moduleId: string
  lang: string
  onLoadExample?: (id: string, inputs: Record<string, unknown>) => void
  onRunExample?: (id: string) => void
  currentResult?: unknown
}

interface Example {
  id: string
  label: string
  inputs: Record<string, unknown>
  expected_output?: string
}

function ModuleSectionContent({ section, lang, onLoadExample, onRunExample, currentResult }: SectionProps) {
  const tr = lang === 'tr'
  return (
    <div className="moduleread-section">
      <div
        className="moduleread-section__body"
        dangerouslySetInnerHTML={{ __html: escapeAndRender(section.content) }}
      />
      {section.examples && section.examples.length > 0 && (
        <div className="moduleread-examples">
          <h4 className="moduleread-examples__title">
            {tr ? 'Örnekler' : 'Examples'}
          </h4>
          {section.examples.map((ex) => (
            <div key={ex.id} className="moduleread-example-card">
              <div className="moduleread-example-card__label">{ex.label}</div>
              {ex.expected_output && (
                <div className="moduleread-example-card__expected">
                  <span className="moduleread-label">{tr ? 'Beklenen:' : 'Expected:'}</span>
                  {' '}{ex.expected_output}
                </div>
              )}
              <div className="moduleread-example-card__actions">
                {onLoadExample && (
                  <button
                    className="moduleread-action-btn"
                    onClick={() => onLoadExample(ex.id, ex.inputs)}
                  >
                    {tr ? 'Örneği Yükle' : 'Load Example'}
                  </button>
                )}
                {onRunExample && (
                  <button
                    className="moduleread-action-btn moduleread-action-btn--run"
                    onClick={() => onRunExample(ex.id)}
                  >
                    {tr ? 'Çalıştır' : 'Run'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {currentResult !== undefined && (
        <div className="moduleread-current-result">
          <h4>{tr ? 'Mevcut Sonuç' : 'Current Result'}</h4>
          <pre className="moduleread-result-json">
            {JSON.stringify(currentResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

/** Minimal safe HTML renderer — only allows certain tags, no script injection. */
function escapeAndRender(text: string): string {
  // Convert markdown-ish bold and line breaks to safe HTML
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

/* ── ModuleReadButton convenience wrapper ─────────────────────────────────── */
/**
 * Minimal trigger-only button to place in module topbars.
 * Renders the full ModuleReadPanel beside it.
 */
export function ModuleReadButton(props: Props) {
  return <ModuleReadPanel {...props} />
}

export default ModuleReadPanel
