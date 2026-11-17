
import { useState } from 'react'
import client from '../api/client'
import { useAppLanguage } from '../i18n/useAppLanguage'
import { ModuleReadButton } from '../components/ModuleReadPanel'

// ── Shared types ──────────────────────────────────────────────────────────────

type LobePoint = {
  current_ka: number
  weld_cycles: number
  nugget_mm: number
  expulsion_risk: number
  fusion_risk: number
  zone: string
}

type StepperStep = {
  spot_count: number
  current_ka: number
  increase_percent: number
}

type ElectrodeLifeResult = {
  estimated_life_spots: number
  recommended_dress_interval_spots: number
  estimated_replacements_per_year: number
  confidence: string
  note: string
  stepper_profile: StepperStep[]
}

type DynamicResistanceResult = {
  sample_count: number
  initial_micro_ohm: number
  peak_micro_ohm: number
  peak_index: number
  final_micro_ohm: number
  mean_micro_ohm: number
  post_peak_drop_ratio: number
  overall_slope: number
  quality: string
  flags: string[]
}

type PulseStrategyResult = {
  strategy: string
  pulse_count: number
  first_pulse_current_ka: number
  main_pulse_current_ka: number
  pre_pulse_cycles: number
  main_pulse_cycles: number
  decision_score: number
  reasons: string[]
  validation_required: boolean
}

type Tab = 'lobe' | 'electrode' | 'resistance' | 'pulse'

const MATERIAL_OPTIONS = [
  'Düşük / Orta Karbonlu Çelik',
  'Galvanizli / Kaplamalı Çelik',
  'AHSS / UHSS / PHS',
  'Paslanmaz Çelik',
  'Alüminyum Alaşımları',
]

const STACK_OPTIONS = ['2T', '3T', '4T']

// ── Resistance chart (inline SVG, no deps) ────────────────────────────────────

function ResistanceChart({ samples }: { samples: number[] }) {
  if (samples.length < 2) return null
  const W = 500, H = 160, PAD = 36
  const max = Math.max(...samples)
  const min = Math.min(...samples)
  const range = max - min || 1
  const pts = samples.map((v, i) => {
    const x = PAD + (i / (samples.length - 1)) * (W - PAD * 2)
    const y = PAD + ((max - v) / range) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const peakIdx = samples.indexOf(max)
  const peakX = PAD + (peakIdx / (samples.length - 1)) * (W - PAD * 2)
  const peakY = PAD

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block', maxHeight: 180 }} aria-label="Resistance profile chart">
      <polyline points={pts.join(' ')} fill="none" stroke="var(--accent, #3b82f6)" strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx={peakX} cy={peakY} r={5} fill="var(--accent, #3b82f6)" />
      <text x={peakX + 6} y={peakY + 4} fontSize="11" fill="var(--muted, #6b7280)">{max.toFixed(1)} µΩ</text>
      <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="var(--border, #e5e7eb)" strokeWidth="1" />
      <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="var(--border, #e5e7eb)" strokeWidth="1" />
      <text x={PAD - 2} y={PAD + 4} fontSize="10" fill="var(--muted, #6b7280)" textAnchor="end">{max.toFixed(0)}</text>
      <text x={PAD - 2} y={H - PAD + 4} fontSize="10" fill="var(--muted, #6b7280)" textAnchor="end">{min.toFixed(0)}</text>
      <text x={W / 2} y={H - 4} fontSize="10" fill="var(--muted, #6b7280)" textAnchor="middle">cycle frame</text>
    </svg>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function EngineeringPage() {
  const { t } = useAppLanguage()
  const ep = t.engineeringLobeLabPage
  const eg = t.engineeringPage

  const [activeTab, setActiveTab] = useState<Tab>('lobe')

  // ── Weld Lobe state ──────────────────────────────────────────────────────
  const [lobeResult, setLobeResult] = useState<{
    optimum: LobePoint | null
    safe_count: number
    warning_count: number
    unsafe_count: number
    sensitivity: Array<Record<string, unknown>>
  } | null>(null)
  const [lobeBusy, setLobeBusy] = useState(false)
  const [lobeError, setLobeError] = useState('')

  async function calculateLobe() {
    setLobeBusy(true)
    setLobeError('')
    try {
      const response = await client.post('/engineering/weld-lobe', {
        material_family: 'Düşük / Orta Karbonlu Çelik',
        thickness_mm: 1.0,
        force_kn: 3.0,
        min_nugget_mm: 4.2,
        current_min_ka: 6.0,
        current_max_ka: 12.0,
        current_step_ka: 0.5,
        time_min_cycles: 8,
        time_max_cycles: 18,
        time_step_cycles: 1,
      })
      setLobeResult(response.data)
    } catch {
      setLobeError(ep.backendUnavailableText)
    } finally {
      setLobeBusy(false)
    }
  }

  // ── Electrode Life state ─────────────────────────────────────────────────
  const [elForm, setElForm] = useState({
    material_family: 'Düşük / Orta Karbonlu Çelik',
    coated: false,
    tip_diameter_mm: 6.0,
    cooling_flow_lpm: 6.0,
    cooling_temp_c: 20.0,
    current_ka: 9.5,
    annual_spot_count: 50000,
  })
  const [elResult, setElResult] = useState<ElectrodeLifeResult | null>(null)
  const [elBusy, setElBusy] = useState(false)
  const [elError, setElError] = useState('')

  async function calculateElectrodeLife() {
    setElBusy(true)
    setElError('')
    try {
      const response = await client.post('/engineering/electrode-life', elForm)
      setElResult(response.data)
    } catch {
      setElError(eg.backendUnavailableText)
    } finally {
      setElBusy(false)
    }
  }

  // ── Dynamic Resistance state ─────────────────────────────────────────────
  const DEFAULT_SAMPLES = '85, 92, 108, 118, 120, 115, 109, 103, 98, 95, 92, 90'
  const [drSamplesText, setDrSamplesText] = useState(DEFAULT_SAMPLES)
  const [drResult, setDrResult] = useState<DynamicResistanceResult | null>(null)
  const [drBusy, setDrBusy] = useState(false)
  const [drError, setDrError] = useState('')
  const [drSamples, setDrSamples] = useState<number[]>([])

  async function analyzeDynamicResistance() {
    const parsed = drSamplesText.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n))
    if (parsed.length < 5) {
      setDrError('At least 5 valid numeric samples required.')
      return
    }
    setDrBusy(true)
    setDrError('')
    setDrSamples(parsed)
    try {
      const response = await client.post('/engineering/dynamic-resistance', {
        samples_micro_ohm: parsed,
      })
      setDrResult(response.data)
    } catch {
      setDrError(eg.backendUnavailableText)
    } finally {
      setDrBusy(false)
    }
  }

  // ── Pulse Strategy state ─────────────────────────────────────────────────
  const [psForm, setPsForm] = useState({
    material_family: 'Düşük / Orta Karbonlu Çelik',
    coated: false,
    thickness_ratio: 1.0,
    stack_count: '2T',
    adhesive: false,
    current_ka: 9.5,
    weld_cycles: 16,
  })
  const [psResult, setPsResult] = useState<PulseStrategyResult | null>(null)
  const [psBusy, setPsBusy] = useState(false)
  const [psError, setPsError] = useState('')

  const MATERIAL_MAP: Record<string, string> = {
    mild_steel: 'Düşük / Orta Karbonlu Çelik',
    galvanized_steel: 'Galvanizli / Kaplamalı Çelik',
    AHSS: 'AHSS / UHSS / PHS',
    stainless_steel: 'Paslanmaz Çelik',
    aluminum_alloys: 'Alüminyum Alaşımları',
  }

  function handleEngineeringLoadExample(id: string, inputs: Record<string, unknown>) {
    if (id === 'electrode_life_mild') {
      const mat = typeof inputs.material_family === 'string'
        ? (MATERIAL_MAP[inputs.material_family] ?? 'Düşük / Orta Karbonlu Çelik')
        : 'Düşük / Orta Karbonlu Çelik'
      setElForm({
        material_family: mat,
        coated: Boolean(inputs.coated),
        tip_diameter_mm: typeof inputs.tip_diameter_mm === 'number' ? inputs.tip_diameter_mm : 6.0,
        cooling_flow_lpm: typeof inputs.cooling_flow_lpm === 'number' ? inputs.cooling_flow_lpm : 2.0,
        cooling_temp_c: typeof inputs.cooling_temp_c === 'number' ? inputs.cooling_temp_c : 20.0,
        current_ka: typeof inputs.current_ka === 'number' ? inputs.current_ka : 8.0,
        annual_spot_count: typeof inputs.annual_spot_count === 'number' ? inputs.annual_spot_count : 50000,
      })
      setActiveTab('electrode')
    } else {
      calculateLobe()
    }
  }

  async function calculatePulseStrategy() {
    setPsBusy(true)
    setPsError('')
    try {
      const response = await client.post('/engineering/pulse-strategy', psForm)
      setPsResult(response.data)
    } catch {
      setPsError(eg.backendUnavailableText)
    } finally {
      setPsBusy(false)
    }
  }

  // ── Shared error/busy renderers ──────────────────────────────────────────

  function ErrorBanner({ msg, title }: { msg: string; title: string }) {
    return (
      <div className="alert danger" role="alert">
        <div>
          <div className="alert-title">{title}</div>
          <div className="alert-text">{msg}</div>
        </div>
      </div>
    )
  }

  function Spinner({ label }: { label: string }) {
    return (
      <div className="state-msg" role="status">
        <div className="spinner" aria-hidden="true" />
        <span>{label}</span>
      </div>
    )
  }

  // ── Tab: Weld Lobe Lab ───────────────────────────────────────────────────

  function WeldLobeTab() {
    return (
      <>
        <div className="page-header" style={{ marginTop: 0 }}>
          <div>
            <p className="subtitle">{ep.subtitle}</p>
          </div>
          <div className="page-actions">
            <ModuleReadButton moduleId="engineering" onLoadExample={handleEngineeringLoadExample} />
            <button className="btn btn-primary" onClick={calculateLobe} disabled={lobeBusy}>
              {lobeBusy ? ep.calculating : ep.calculateBtn}
            </button>
          </div>
        </div>
        <div className="ws-context-bar" aria-label="Engineering context">
          <span className="ctx-chip accent">{ep.authorityChip.split(':')[0]}: <strong>{ep.authorityChip.split(':')[1]?.trim()}</strong></span>
          <span className="ctx-chip">Method: <strong>{ep.methodChip.split(':')[1]?.trim()}</strong></span>
          <span className="ctx-chip">Curves: <strong>{ep.curvesChip.split(':')[1]?.trim()}</strong></span>
        </div>
        {lobeError && <ErrorBanner msg={lobeError} title={ep.backendUnavailableTitle} />}
        {lobeBusy && <Spinner label={ep.calculatingVerbose} />}
        {!lobeResult && !lobeBusy && (
          <div className="ws-grid-main">
            <section className="panel" aria-label="Engineering context">
              <div className="panel-header">
                <h3>{ep.contextTitle}</h3>
                <span className="panel-meta">{ep.contextMeta}</span>
              </div>
              <div className="panel-body">
                <div className="trace-block">
                  <div className="trace-row"><span className="label">Material</span><span className="value">{ep.contextMaterial}</span></div>
                  <div className="trace-row"><span className="label">Force</span><span className="value">{ep.contextForce}</span></div>
                  <div className="trace-row"><span className="label">Current sweep</span><span className="value">{ep.contextCurrentSweep}</span></div>
                  <div className="trace-row"><span className="label">Time sweep</span><span className="value">{ep.contextTimeSweep}</span></div>
                </div>
              </div>
              <div className="panel-footer">{ep.contextFooter}</div>
            </section>
            <section className="panel" aria-label="Process window workspace">
              <div className="panel-header">
                <h3>{ep.processWindowTitle}</h3>
                <span className="panel-meta">{ep.processWindowMeta}</span>
              </div>
              <div className="panel-body">
                <div className="chart-ready" role="status">
                  <div className="chart-frame" aria-hidden="true">
                    <div className="chart-axes" />
                    <div className="chart-caption">Current × Time · safe-window frame</div>
                  </div>
                  <strong>{ep.noDataMessage}</strong>
                  <span>{ep.noDataHint}</span>
                  <span className="empty-action">{ep.noDataAction}</span>
                </div>
              </div>
              <div className="panel-footer">{ep.processWindowFooter}</div>
            </section>
          </div>
        )}
        {lobeResult && !lobeBusy && (
          <div className="ws-grid-main">
            <section className="panel" aria-label="Process window summary">
              <div className="panel-header">
                <h3>{ep.summaryTitle}</h3>
                <span className="panel-meta">{ep.summaryMeta}</span>
              </div>
              <div className="panel-body">
                <div className="grid-2">
                  <article className="metric-card state-ok">
                    <span className="metric-label">{ep.safeCount}</span>
                    <strong className="metric-value">{lobeResult.safe_count}</strong>
                  </article>
                  <article className="metric-card state-warn">
                    <span className="metric-label">{ep.warningCount}</span>
                    <strong className="metric-value">{lobeResult.warning_count}</strong>
                  </article>
                  <article className="metric-card state-danger">
                    <span className="metric-label">{ep.unsafeCount}</span>
                    <strong className="metric-value">{lobeResult.unsafe_count}</strong>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{ep.optimumPoint}</span>
                    <strong className="metric-value" style={{ fontSize: 'var(--fs-h4)' }}>
                      {lobeResult.optimum ? `${lobeResult.optimum.current_ka} kA / ${lobeResult.optimum.weld_cycles} cyc` : '—'}
                    </strong>
                  </article>
                </div>
              </div>
              <div className="panel-footer">{ep.summaryFooter}</div>
            </section>
            <section className="panel" aria-label={ep.sensitivityTitle}>
              <div className="panel-header">
                <h3>{ep.sensitivityTitle}</h3>
                <span className="panel-meta">{ep.sensitivityMeta}</span>
              </div>
              <div className="panel-body">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{ep.sensitivityRank}</th>
                      <th>{ep.sensitivityParam}</th>
                      <th>{ep.sensitivityImpact}</th>
                      <th>{ep.sensitivitySensitivity}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lobeResult.sensitivity.map((row) => (
                      <tr key={String(row.parameter)}>
                        <td className="mono">{String(row.priority_rank)}</td>
                        <td>{String(row.parameter)}</td>
                        <td className="mono">{String(row.absolute_impact)}</td>
                        <td className="mono">{String(row.sensitivity_mm_per_unit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="panel-footer">{ep.sensitivityFooter}</div>
            </section>
          </div>
        )}
      </>
    )
  }

  // ── Tab: Electrode Life ──────────────────────────────────────────────────

  function ElectrodeLifeTab() {
    return (
      <>
        <div className="page-header" style={{ marginTop: 0 }}>
          <div>
            <p className="subtitle">{eg.elSubtitle}</p>
          </div>
          <div className="page-actions">
            <button className="btn btn-primary" onClick={calculateElectrodeLife} disabled={elBusy}>
              {elBusy ? eg.elCalculating : eg.elCalculateBtn}
            </button>
          </div>
        </div>
        {elError && <ErrorBanner msg={elError} title={eg.backendUnavailableTitle} />}
        {elBusy && <Spinner label={eg.elCalculating} />}
        <div className="ws-grid-main">
          <section className="panel" aria-label="Electrode life inputs">
            <div className="panel-header">
              <h3>{eg.elTitle}</h3>
              <span className="panel-meta">input</span>
            </div>
            <div className="panel-body">
              <div className="trace-block">
                <div className="form-row">
                  <label className="form-label">{eg.elMaterialLabel}</label>
                  <select className="form-control" value={elForm.material_family}
                    onChange={e => setElForm(f => ({ ...f, material_family: e.target.value }))}>
                    {MATERIAL_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elCoatedLabel}</label>
                  <input type="checkbox" checked={elForm.coated}
                    onChange={e => setElForm(f => ({ ...f, coated: e.target.checked }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elTipDiamLabel}</label>
                  <input className="form-control" type="number" step="0.5" min="4" max="16"
                    value={elForm.tip_diameter_mm}
                    onChange={e => setElForm(f => ({ ...f, tip_diameter_mm: parseFloat(e.target.value) || f.tip_diameter_mm }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elCoolingFlowLabel}</label>
                  <input className="form-control" type="number" step="0.5" min="0" max="20"
                    value={elForm.cooling_flow_lpm}
                    onChange={e => setElForm(f => ({ ...f, cooling_flow_lpm: parseFloat(e.target.value) || f.cooling_flow_lpm }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elCoolingTempLabel}</label>
                  <input className="form-control" type="number" step="1" min="5" max="60"
                    value={elForm.cooling_temp_c}
                    onChange={e => setElForm(f => ({ ...f, cooling_temp_c: parseFloat(e.target.value) || f.cooling_temp_c }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elCurrentLabel}</label>
                  <input className="form-control" type="number" step="0.5" min="4" max="20"
                    value={elForm.current_ka}
                    onChange={e => setElForm(f => ({ ...f, current_ka: parseFloat(e.target.value) || f.current_ka }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.elAnnualSpotsLabel}</label>
                  <input className="form-control" type="number" step="1000" min="100" max="1000000"
                    value={elForm.annual_spot_count}
                    onChange={e => setElForm(f => ({ ...f, annual_spot_count: parseInt(e.target.value) || f.annual_spot_count }))} />
                </div>
              </div>
            </div>
            <div className="panel-footer">{eg.elModelLimitationNote}</div>
          </section>

          {elResult && !elBusy && (
            <section className="panel" aria-label="Electrode life results">
              <div className="panel-header">
                <h3>{eg.elTitle}</h3>
                <span className="panel-meta">result</span>
              </div>
              <div className="panel-body">
                <div className="grid-2">
                  <article className="metric-card">
                    <span className="metric-label">{eg.elEstimatedLifeLabel}</span>
                    <strong className="metric-value">{elResult.estimated_life_spots.toLocaleString()}</strong>
                    <span className="metric-unit">spots</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.elDressIntervalLabel}</span>
                    <strong className="metric-value">{elResult.recommended_dress_interval_spots.toLocaleString()}</strong>
                    <span className="metric-unit">spots</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.elReplacementsLabel}</span>
                    <strong className="metric-value">{elResult.estimated_replacements_per_year}</strong>
                    <span className="metric-unit">caps/yr</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.elConfidenceLabel}</span>
                    <strong className="metric-value" style={{ fontSize: 'var(--fs-h4)' }}>{elResult.confidence}</strong>
                  </article>
                </div>
                <div className="alert info" style={{ marginTop: 12 }} role="note">
                  <div className="alert-text">{elResult.note}</div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <div className="panel-header" style={{ padding: 0, marginBottom: 8 }}>
                    <h4 style={{ margin: 0, fontSize: 'var(--fs-sm)' }}>{eg.elStepperProfileTitle}</h4>
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{eg.elSpotCountCol}</th>
                        <th>{eg.elCurrentKaCol}</th>
                        <th>{eg.elIncreaseCol}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {elResult.stepper_profile.map((step, i) => (
                        <tr key={i}>
                          <td className="mono">{step.spot_count.toLocaleString()}</td>
                          <td className="mono">{step.current_ka.toFixed(2)}</td>
                          <td className="mono">{step.increase_percent.toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="panel-footer">{eg.elModelLimitationNote}</div>
            </section>
          )}
        </div>
      </>
    )
  }

  // ── Tab: Dynamic Resistance ──────────────────────────────────────────────

  function DynamicResistanceTab() {
    const qualityClass: Record<string, string> = {
      'Normal': 'state-ok',
      'İnceleme Gerekli': 'state-warn',
      'Yüksek Risk': 'state-danger',
    }
    return (
      <>
        <div className="page-header" style={{ marginTop: 0 }}>
          <div>
            <p className="subtitle">{eg.drSubtitle}</p>
          </div>
          <div className="page-actions">
            <button className="btn btn-primary" onClick={analyzeDynamicResistance} disabled={drBusy}>
              {drBusy ? eg.drCalculating : eg.drCalculateBtn}
            </button>
          </div>
        </div>
        {drError && <ErrorBanner msg={drError} title={eg.backendUnavailableTitle} />}
        {drBusy && <Spinner label={eg.drCalculating} />}
        <div className="ws-grid-main">
          <section className="panel" aria-label="Dynamic resistance input">
            <div className="panel-header">
              <h3>{eg.drTitle}</h3>
              <span className="panel-meta">input</span>
            </div>
            <div className="panel-body">
              <div className="form-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                <label className="form-label">{eg.drSamplesLabel}</label>
                <div className="form-hint" style={{ color: 'var(--muted)', fontSize: 'var(--fs-sm)', marginBottom: 4 }}>
                  {eg.drSamplesHint}
                </div>
                <textarea
                  className="form-control"
                  rows={3}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: 13 }}
                  value={drSamplesText}
                  onChange={e => setDrSamplesText(e.target.value)}
                  aria-label="Resistance samples in µΩ"
                />
              </div>
              {drSamples.length >= 2 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--muted)', marginBottom: 6 }}>
                    {eg.drChartTitle} · {eg.drChartNote}
                  </div>
                  <ResistanceChart samples={drSamples} />
                </div>
              )}
            </div>
            <div className="panel-footer">{eg.drModelLimitationNote}</div>
          </section>

          {drResult && !drBusy && (
            <section className="panel" aria-label="Dynamic resistance results">
              <div className="panel-header">
                <h3>{eg.drTitle}</h3>
                <span className="panel-meta">result</span>
              </div>
              <div className="panel-body">
                <div className="grid-2">
                  <article className={`metric-card ${qualityClass[drResult.quality] || ''}`}>
                    <span className="metric-label">{eg.drQualityLabel}</span>
                    <strong className="metric-value" style={{ fontSize: 'var(--fs-h4)' }}>{drResult.quality}</strong>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drPeakLabel}</span>
                    <strong className="metric-value">{drResult.peak_micro_ohm.toFixed(1)}</strong>
                    <span className="metric-unit">µΩ</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drInitialLabel}</span>
                    <strong className="metric-value">{drResult.initial_micro_ohm.toFixed(1)}</strong>
                    <span className="metric-unit">µΩ</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drFinalLabel}</span>
                    <strong className="metric-value">{drResult.final_micro_ohm.toFixed(1)}</strong>
                    <span className="metric-unit">µΩ</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drMeanLabel}</span>
                    <strong className="metric-value">{drResult.mean_micro_ohm.toFixed(1)}</strong>
                    <span className="metric-unit">µΩ</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drDropRatioLabel}</span>
                    <strong className="metric-value">{(drResult.post_peak_drop_ratio * 100).toFixed(1)}</strong>
                    <span className="metric-unit">%</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.drSlopeLabel}</span>
                    <strong className="metric-value">{drResult.overall_slope.toFixed(3)}</strong>
                    <span className="metric-unit">µΩ/frame</span>
                  </article>
                </div>
                {drResult.flags.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, marginBottom: 6 }}>{eg.drFlagsTitle}</div>
                    <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 'var(--fs-sm)' }}>
                      {drResult.flags.map((flag, i) => (
                        <li key={i} style={{ color: 'var(--warn, #d97706)', marginBottom: 4 }}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {drSamples.length >= 2 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--muted)', marginBottom: 6 }}>
                      {eg.drChartTitle} · {eg.drChartNote}
                    </div>
                    <ResistanceChart samples={drSamples} />
                  </div>
                )}
              </div>
              <div className="panel-footer">{eg.drModelLimitationNote}</div>
            </section>
          )}
        </div>
      </>
    )
  }

  // ── Tab: Pulse Strategy ──────────────────────────────────────────────────

  function PulseStrategyTab() {
    return (
      <>
        <div className="page-header" style={{ marginTop: 0 }}>
          <div>
            <p className="subtitle">{eg.psSubtitle}</p>
          </div>
          <div className="page-actions">
            <button className="btn btn-primary" onClick={calculatePulseStrategy} disabled={psBusy}>
              {psBusy ? eg.psCalculating : eg.psCalculateBtn}
            </button>
          </div>
        </div>
        {psError && <ErrorBanner msg={psError} title={eg.backendUnavailableTitle} />}
        {psBusy && <Spinner label={eg.psCalculating} />}
        <div className="ws-grid-main">
          <section className="panel" aria-label="Pulse strategy inputs">
            <div className="panel-header">
              <h3>{eg.psTitle}</h3>
              <span className="panel-meta">input</span>
            </div>
            <div className="panel-body">
              <div className="trace-block">
                <div className="form-row">
                  <label className="form-label">{eg.psMaterialLabel}</label>
                  <select className="form-control" value={psForm.material_family}
                    onChange={e => setPsForm(f => ({ ...f, material_family: e.target.value }))}>
                    {MATERIAL_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psCoatedLabel}</label>
                  <input type="checkbox" checked={psForm.coated}
                    onChange={e => setPsForm(f => ({ ...f, coated: e.target.checked }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psThicknessRatioLabel}</label>
                  <input className="form-control" type="number" step="0.1" min="1" max="5"
                    value={psForm.thickness_ratio}
                    onChange={e => setPsForm(f => ({ ...f, thickness_ratio: parseFloat(e.target.value) || f.thickness_ratio }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psStackCountLabel}</label>
                  <select className="form-control" value={psForm.stack_count}
                    onChange={e => setPsForm(f => ({ ...f, stack_count: e.target.value }))}>
                    {STACK_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psAdhesiveLabel}</label>
                  <input type="checkbox" checked={psForm.adhesive}
                    onChange={e => setPsForm(f => ({ ...f, adhesive: e.target.checked }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psCurrentLabel}</label>
                  <input className="form-control" type="number" step="0.5" min="4" max="20"
                    value={psForm.current_ka}
                    onChange={e => setPsForm(f => ({ ...f, current_ka: parseFloat(e.target.value) || f.current_ka }))} />
                </div>
                <div className="form-row">
                  <label className="form-label">{eg.psWeldCyclesLabel}</label>
                  <input className="form-control" type="number" step="1" min="1" max="60"
                    value={psForm.weld_cycles}
                    onChange={e => setPsForm(f => ({ ...f, weld_cycles: parseInt(e.target.value) || f.weld_cycles }))} />
                </div>
              </div>
            </div>
            <div className="panel-footer">{eg.psModelLimitationNote}</div>
          </section>

          {psResult && !psBusy && (
            <section className="panel" aria-label="Pulse strategy results">
              <div className="panel-header">
                <h3>{eg.psTitle}</h3>
                <span className="panel-meta">result</span>
              </div>
              <div className="panel-body">
                <div className="grid-2">
                  <article className="metric-card" style={{ gridColumn: '1 / -1' }}>
                    <span className="metric-label">{eg.psStrategyLabel}</span>
                    <strong className="metric-value" style={{ fontSize: 'var(--fs-h4)' }}>{psResult.strategy}</strong>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.psPulseCountLabel}</span>
                    <strong className="metric-value">{psResult.pulse_count}</strong>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.psDecisionScoreLabel}</span>
                    <strong className="metric-value">{psResult.decision_score}</strong>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.psFirstPulseCurrentLabel}</span>
                    <strong className="metric-value">{psResult.first_pulse_current_ka.toFixed(2)}</strong>
                    <span className="metric-unit">kA</span>
                  </article>
                  <article className="metric-card">
                    <span className="metric-label">{eg.psMainPulseCurrentLabel}</span>
                    <strong className="metric-value">{psResult.main_pulse_current_ka.toFixed(2)}</strong>
                    <span className="metric-unit">kA</span>
                  </article>
                  {psResult.pulse_count > 1 && (
                    <>
                      <article className="metric-card">
                        <span className="metric-label">{eg.psPrePulseCyclesLabel}</span>
                        <strong className="metric-value">{psResult.pre_pulse_cycles}</strong>
                        <span className="metric-unit">cyc</span>
                      </article>
                      <article className="metric-card">
                        <span className="metric-label">{eg.psMainPulseCyclesLabel}</span>
                        <strong className="metric-value">{psResult.main_pulse_cycles}</strong>
                        <span className="metric-unit">cyc</span>
                      </article>
                    </>
                  )}
                </div>
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, marginBottom: 6 }}>{eg.psReasonsTitle}</div>
                  <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 'var(--fs-sm)' }}>
                    {psResult.reasons.map((r, i) => <li key={i} style={{ marginBottom: 4 }}>{r}</li>)}
                  </ul>
                </div>
                {psResult.validation_required && (
                  <div className="alert warn" style={{ marginTop: 12 }} role="note">
                    <div className="alert-text">{eg.psValidationNote}</div>
                  </div>
                )}
              </div>
              <div className="panel-footer">{eg.psModelLimitationNote}</div>
            </section>
          )}
        </div>
      </>
    )
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const tabs: { id: Tab; label: string }[] = [
    { id: 'lobe',       label: eg.tabWeldLobe },
    { id: 'electrode',  label: eg.tabElectrodeLife },
    { id: 'resistance', label: eg.tabDynamicResistance },
    { id: 'pulse',      label: eg.tabPulseStrategy },
  ]

  return (
    <div className="page active">
      <div className="ws-kicker">{eg.kicker}</div>
      <header className="page-header">
        <div>
          <h1>{
            activeTab === 'lobe' ? ep.title :
            activeTab === 'electrode' ? eg.elTitle :
            activeTab === 'resistance' ? eg.drTitle :
            eg.psTitle
          }</h1>
        </div>
      </header>

      {/* Tab bar */}
      <div className="tab-bar" role="tablist" aria-label="Engineering sub-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {activeTab === 'lobe'       && <WeldLobeTab />}
        {activeTab === 'electrode'  && <ElectrodeLifeTab />}
        {activeTab === 'resistance' && <DynamicResistanceTab />}
        {activeTab === 'pulse'      && <PulseStrategyTab />}
      </div>
    </div>
  )
}
