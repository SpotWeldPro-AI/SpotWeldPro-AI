# ModuleRead Architecture

**PLATFORM-SYNTH-QA-MODULEREAD-01 — Phase F/G/H**  
Version: 1.0.0 | Date: 2026-11-17

## Overview

ModuleRead is a bilingual (TR/EN) contextual help and tutorial system embedded in every application module. It provides users with module documentation, worked examples, and interactive commands from a resizable right-side drawer panel — without navigating away from their current module.

## Component Structure

```
frontend/src/
├── components/
│   └── ModuleReadPanel.tsx     # Core component (panel + button)
├── moduleread/
│   └── registry.ts             # Bilingual content registry
└── styles.css                  # ModuleRead CSS (appended)
```

## ModuleReadPanel.tsx

### Exports
- `ModuleReadPanel` — full panel component
- `ModuleReadButton` — convenience wrapper (renders ModuleReadPanel)

### Props (Props interface)
| Prop | Type | Description |
|------|------|-------------|
| `moduleId` | `string` | Key into the content registry |
| `onLoadExample` | `(id, inputs) => void` | Optional — loads example inputs into module form |
| `onRunExample` | `(id) => void` | Optional — triggers module calculation |
| `currentResult` | `unknown` | Optional — shows current result JSON in panel |

### Panel Modes
| Mode | Behavior |
|------|----------|
| `compact` | Fixed 300px width |
| `wide` (default) | Resizable 280–900px, persisted in `localStorage` |
| `fullscreen` | 100vw, covers full viewport |

### Accessibility
- `role="dialog"`, `aria-modal="true"`, `aria-label`
- Escape key closes and returns focus to trigger button
- Keyboard resize: ArrowLeft/ArrowRight on resize handle
- Focus trap via `tabIndex={-1}` on dialog ref
- `aria-pressed` on mode buttons, `aria-expanded` on trigger

### localStorage Persistence
- Key: `spotweldpro_moduleread_width`
- Wrapped in try/catch — graceful fallback to 420px default
- Persists width on `mouseup` after drag

### Security
- `escapeAndRender()` escapes HTML entities before rendering content
- Supports `**bold**` and `` `code` `` markdown conversion only
- No XSS vectors — no raw HTML passthrough

### Confirm Replace Dialog
- Shown before `onLoadExample` fires
- User must confirm before form values are overwritten
- Prevents accidental data loss in form-heavy modules

## registry.ts

### Interfaces
```typescript
interface ModuleReadContent {
  module_id: string
  title_tr: string
  title_en: string
  version: string
  sections_tr: Section[]
  sections_en: Section[]
}

interface Section {
  title: string
  content: string    // markdown-ish, safe rendered
  examples?: Example[]
}

interface Example {
  id: string
  label: string
  inputs: Record<string, unknown>
  expected_output?: string
}
```

### Exports
- `getModuleContent(id: string): ModuleReadContent | null`
- `listSupportedModules(): string[]`

## Module Coverage

| Module ID | Page | Status |
|-----------|------|--------|
| `dashboard` | DashboardPage | Full content |
| `analysis` | AnalysisPage | Full content + loadExample |
| `engineering` | EngineeringPage | Full content |
| `failure` | FailureProbabilityPage | Full content |
| `statistical` | StatisticalAnalysisPage | Full content |
| `energy` | EnergyPage | Full content |
| `inspection` | StaticInspectionPage | Full content |
| `live` | LiveMonitoringPage | Full content |
| `models` | ModelCatalogPage | Full content |
| `annotation` | AnnotationPage | Stub |
| `dataset_dashboard` | DatasetDashboardPage | Stub |
| `conflict_review` | ConflictReviewPage | Stub |
| `projects` | ProjectsPage | Stub |
| `help` | HelpCenterPage | Stub |

Stubs show availability badge "Coming Soon" and do not render a disabled button — they render the button with limited content.

## CSS Architecture

All ModuleRead CSS is appended to `frontend/src/styles.css` with the prefix `.moduleread-`.

| Class | Purpose |
|-------|---------|
| `.moduleread-btn` | Trigger button in module topbar |
| `.moduleread-btn--unavailable` | Disabled state (no content) |
| `.moduleread-backdrop` | Fixed overlay (z-index 1100) |
| `.moduleread-panel` | Drawer container |
| `.moduleread-panel--fullscreen` | Full viewport mode |
| `.moduleread-panel--compact` | 300px fixed mode |
| `.moduleread-resize-handle` | Drag handle (6px wide, col-resize cursor) |
| `.moduleread-section-tab` | Section navigation tabs |
| `.moduleread-example-card` | Individual example cards |
| `.moduleread-action-btn` | Load Example / Run buttons |

**Mobile breakpoint**: at `<600px`, panel slides up from bottom as `85vh` bottom sheet.

## Internationalization

Language follows the app's `useAppLanguage()` hook — `lang === 'tr'` selects Turkish content, `'en'` selects English. Users change language via the global language toggle; no separate language control inside the panel.

## Known Limitations

1. `onLoadExample` wired only on `AnalysisPage` (uses `setP`). Other pages with forms need tab-aware wiring for multi-step form population.
2. Stub modules have minimal content — planned for Phase G expansion.
3. No backend storage for ModuleRead interaction telemetry (Phase H future work).
