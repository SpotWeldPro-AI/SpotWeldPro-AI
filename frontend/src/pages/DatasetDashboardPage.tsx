/**
 * VISION-P3E: Dataset Quality Dashboard.
 *
 * Shows:
 *  - Annotation counts by review status
 *  - Contamination distribution
 *  - Conflict adjudication progress
 *  - Training gate (E1–E4) indicators
 *  - Conflict pair list with adjudication controls
 *  - Export panel (quality_engineer / system_admin only)
 *
 * Training gate is always shown as BLOCKED until DatasetAudit gates clear.
 */
import { useState, useEffect } from 'react'
import { useAppLanguage } from '../i18n/useAppLanguage'
import { getAuthHeaders } from '../api/client'
import { ModuleReadButton } from '../components/ModuleReadPanel'

const API = '/api/v1/annotation'

interface Metrics {
  annotation_status_counts: Record<string, number>
  contamination_distribution: Record<string, number>
  approved_findings_by_code: Record<string, number>
  conflict_total: number
  conflict_pending: number
  conflict_resolved: number
  export_eligible_count: number
  training_gate_open: boolean
  training_blocked_reason: string | null
  e1_e4_gates: Record<string, boolean>
}

interface Conflict {
  id: number
  sha1_16: string
  path_a: string
  path_b: string
  label_a: string
  label_b: string
  split_a: string
  split_b: string
  conflict_type: string
  source_archive_a: string
  source_archive_b: string
  decision: string
  adjudicator_id: string | null
  adjudication_notes: string
  adjudicated_at: string | null
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: '#6b7280', SUBMITTED: '#3b82f6', APPROVED: '#22c55e',
  REJECTED: '#ef4444', NEEDS_REVISION: '#f59e0b',
}
const CONTAM_COLORS: Record<string, string> = {
  CLEAN: '#22c55e', LOW: '#84cc16', MEDIUM: '#f59e0b', HIGH: '#ef4444', UNKNOWN: '#6b7280',
}

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: '#1f2937', borderRadius: 8, padding: '14px 18px', minWidth: 110, flex: '1 1 110px' }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || '#f9fafb' }}>{value}</div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function GateIndicator({ label, passed, blocked_reason }: { label: string; passed: boolean; blocked_reason?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                  background: passed ? '#14532d22' : '#7f1d1d22',
                  border: '1px solid ' + (passed ? '#16a34a' : '#dc2626'),
                  borderRadius: 6, marginBottom: 6 }}>
      <span style={{ fontSize: 16, color: passed ? '#22c55e' : '#ef4444' }}>{passed ? '✓' : '✗'}</span>
      <div>
        <div style={{ fontSize: 12, color: passed ? '#86efac' : '#fca5a5' }}>{label}</div>
        {!passed && blocked_reason && (
          <div style={{ fontSize: 10, color: '#6b7280', marginTop: 1 }}>{blocked_reason}</div>
        )}
      </div>
    </div>
  )
}

export function DatasetDashboardPage() {
  const { lang } = useAppLanguage()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [conflictTotal, setConflictTotal] = useState(0)
  const [filterDecision, setFilterDecision] = useState('PENDING')
  const [adjNotes, setAdjNotes] = useState<Record<number, string>>({})
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [loadingConflicts, setLoadingConflicts] = useState(false)
  const [error, setError] = useState('')
  const [exportVersion, setExportVersion] = useState('')
  const [exportResult, setExportResult] = useState<Record<string, unknown> | null>(null)
  const [exporting, setExporting] = useState(false)

  const authHeaders = getAuthHeaders()

  async function fetchMetrics() {
    setLoadingMetrics(true)
    setError('')
    try {
      const res = await fetch(`${API}/dashboard`, { headers: authHeaders })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setMetrics(await res.json())
    } catch {
      setError(lang === 'tr' ? 'Metrikler yüklenemedi.' : 'Failed to load metrics.')
    } finally { setLoadingMetrics(false) }
  }

  async function fetchConflicts() {
    setLoadingConflicts(true)
    try {
      const params = new URLSearchParams({ limit: '50', offset: '0' })
      if (filterDecision) params.set('decision', filterDecision)
      const res = await fetch(`${API}/conflicts?${params}`, { headers: authHeaders })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setConflicts(data.items)
      setConflictTotal(data.total)
    } catch {
      setError(lang === 'tr' ? 'Çakışmalar yüklenemedi.' : 'Failed to load conflicts.')
    } finally { setLoadingConflicts(false) }
  }

  useEffect(() => { fetchMetrics(); fetchConflicts() }, [])
  useEffect(() => { fetchConflicts() }, [filterDecision])

  async function adjudicate(conflictId: number, decision: string) {
    try {
      const res = await fetch(`${API}/conflicts/${conflictId}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, notes: adjNotes[conflictId] || '' }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error') }
      await fetchConflicts()
      await fetchMetrics()
    } catch (e: unknown) {
      setError(String(e instanceof Error ? e.message : e))
    }
  }

  async function doExport() {
    if (!exportVersion.trim()) {
      setError(lang === 'tr' ? 'Dışa aktarım sürümü gerekli.' : 'Export version is required.'); return
    }
    setExporting(true); setExportResult(null); setError('')
    try {
      const res = await fetch(`${API}/export`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ export_version: exportVersion }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error') }
      setExportResult(await res.json())
    } catch (e: unknown) {
      setError(String(e instanceof Error ? e.message : e))
    } finally { setExporting(false) }
  }

  const statusEntries = metrics ? Object.entries(metrics.annotation_status_counts) : []
  const contamEntries = metrics ? Object.entries(metrics.contamination_distribution) : []
  const findingEntries = metrics ? Object.entries(metrics.approved_findings_by_code).sort((a, b) => b[1] - a[1]) : []

  return (
    <div style={{ padding: '20px 24px', overflowY: 'auto', height: '100%', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 4 }}>
        <h1 style={{ margin: 0, fontSize: 20, color: '#f9fafb', flex: 1 }}>
          {lang === 'tr' ? 'Veri Seti Kalite Panosu' : 'Dataset Quality Dashboard'}
        </h1>
        <ModuleReadButton moduleId="dataset_dashboard" />
      </div>
      <p style={{ margin: '0 0 20px', fontSize: 13, color: '#9ca3af' }}>
        VISION-P3E · {lang === 'tr' ? 'V5 Veri Seti Remediasyon Durumu' : 'V5 Dataset Remediation Status'}
      </p>

      {error && (
        <div style={{ marginBottom: 16, padding: '10px 14px', background: '#7f1d1d22',
                      border: '1px solid #dc2626', borderRadius: 6, color: '#f87171', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Training gate banner */}
      <div style={{ marginBottom: 20, padding: '12px 16px', background: '#78350f22',
                    border: '1px solid #b45309', borderRadius: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#fbbf24', marginBottom: 4 }}>
          ⚠ {lang === 'tr' ? 'Model Eğitimi Engellendi' : 'Model Training Blocked'}
        </div>
        <div style={{ fontSize: 12, color: '#fcd34d' }}>
          {lang === 'tr'
            ? 'DatasetAudit.is_training_allowed() = False. Tüm E1–E4 kapıları çözümlenene kadar eğitim başlatılamaz.'
            : 'DatasetAudit.is_training_allowed() = False. Training cannot start until all E1–E4 gates are resolved.'}
        </div>
      </div>

      {/* E1–E4 gates */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
          {lang === 'tr' ? 'Kalite Kapıları' : 'Quality Gates'}
        </h2>
        {metrics ? (
          <>
            <GateIndicator
              label={lang === 'tr' ? 'E1: Çift / Çakışan Etiket Çözümü' : 'E1: Duplicate/Label-Conflict Resolution'}
              passed={metrics.e1_e4_gates.E1_duplicate_resolution}
              blocked_reason={lang === 'tr'
                ? `${metrics.conflict_pending} bekleyen çakışma`
                : `${metrics.conflict_pending} pending conflicts`}
            />
            <GateIndicator
              label={lang === 'tr' ? 'E2: Annotasyon İşareti Temizliği' : 'E2: Annotation Markup Cleanup'}
              passed={metrics.e1_e4_gates.E2_annotation_cleanup}
              blocked_reason={lang === 'tr' ? 'Manuel doğrulama gerekli' : 'Manual verification required'}
            />
            <GateIndicator
              label={lang === 'tr' ? 'E3: Tekrarsız Bölünme Yeniden Oluşturma' : 'E3: Dedup-Safe Split Regeneration'}
              passed={metrics.e1_e4_gates.E3_split_regenerated}
              blocked_reason={lang === 'tr' ? 'Yeni bölünme henüz oluşturulmadı' : 'New split not yet generated'}
            />
            <GateIndicator
              label={lang === 'tr' ? 'E4: Kaynak Belgelendirme ve İmzalama' : 'E4: Provenance Documentation & Sign-Off'}
              passed={metrics.e1_e4_gates.E4_provenance_documented}
              blocked_reason={lang === 'tr' ? 'Belgelendirme tamamlanmadı' : 'Documentation not completed'}
            />
          </>
        ) : loadingMetrics ? (
          <div style={{ color: '#9ca3af', fontSize: 12 }}>{lang === 'tr' ? 'Yükleniyor…' : 'Loading…'}</div>
        ) : null}
      </section>

      {/* Summary stats */}
      {metrics && (
        <>
          <section style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
              {lang === 'tr' ? 'Annotasyon Özeti' : 'Annotation Summary'}
            </h2>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {statusEntries.map(([status, count]) => (
                <StatCard key={status} label={status} value={count} color={STATUS_COLORS[status]} />
              ))}
              <StatCard
                label={lang === 'tr' ? 'Dışa Aktarıma Uygun' : 'Export Eligible'}
                value={metrics.export_eligible_count}
                color="#22c55e"
              />
            </div>
          </section>

          <section style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
              {lang === 'tr' ? 'Kirlilik Dağılımı' : 'Contamination Distribution'}
            </h2>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {contamEntries.map(([level, count]) => (
                <StatCard key={level} label={level} value={count} color={CONTAM_COLORS[level]} />
              ))}
            </div>
          </section>

          {findingEntries.length > 0 && (
            <section style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
                {lang === 'tr' ? 'Onaylı Bulgular (Hata Koduna Göre)' : 'Approved Findings by Defect Code'}
              </h2>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {findingEntries.map(([code, count]) => (
                  <StatCard key={code} label={code} value={count} />
                ))}
              </div>
            </section>
          )}

          <section style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
              {lang === 'tr' ? 'Çakışma Çözümü' : 'Conflict Resolution'}
            </h2>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
              <StatCard
                label={lang === 'tr' ? 'Toplam Çakışma' : 'Total Conflicts'}
                value={metrics.conflict_total}
              />
              <StatCard
                label={lang === 'tr' ? 'Bekleyen' : 'Pending'}
                value={metrics.conflict_pending}
                color={metrics.conflict_pending > 0 ? '#ef4444' : '#22c55e'}
              />
              <StatCard
                label={lang === 'tr' ? 'Çözümlendi' : 'Resolved'}
                value={metrics.conflict_resolved}
                color="#22c55e"
              />
            </div>
          </section>
        </>
      )}

      {/* Conflict adjudication list */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
          {lang === 'tr' ? 'Çakışma Çifti Karara Bağlama' : 'Conflict Pair Adjudication'}
          {conflictTotal > 0 && <span style={{ color: '#9ca3af', marginLeft: 8, fontWeight: 400 }}>({conflictTotal})</span>}
        </h2>
        <div style={{ marginBottom: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
          <select value={filterDecision} onChange={(e) => setFilterDecision(e.target.value)}
            style={{ fontSize: 12, background: '#1f2937', color: '#d1d5db',
                     border: '1px solid #374151', borderRadius: 4, padding: '4px 8px' }}>
            <option value="">— {lang === 'tr' ? 'Tüm Kararlar' : 'All Decisions'} —</option>
            {['PENDING', 'KEEP_A', 'KEEP_B', 'KEEP_BOTH', 'EXCLUDE_BOTH'].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

        {loadingConflicts && (
          <div style={{ color: '#9ca3af', fontSize: 12 }}>{lang === 'tr' ? 'Yükleniyor…' : 'Loading…'}</div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {conflicts.map((c) => (
            <div key={c.id} style={{ background: '#1f2937', borderRadius: 8, padding: '12px 14px' }}>
              <div style={{ display: 'flex', gap: 16, marginBottom: 8, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 2 }}>
                    Path A · <span style={{ color: '#3b82f6' }}>{c.split_a}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#d1d5db', wordBreak: 'break-all' }}>
                    {c.path_a.split(/[\\/]/).pop()}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#f59e0b', marginTop: 2 }}>
                    {c.label_a}
                  </div>
                </div>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 2 }}>
                    Path B · <span style={{ color: '#3b82f6' }}>{c.split_b}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#d1d5db', wordBreak: 'break-all' }}>
                    {c.path_b.split(/[\\/]/).pop()}
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#f59e0b', marginTop: 2 }}>
                    {c.label_b}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 6 }}>
                SHA1: {c.sha1_16} · Type: {c.conflict_type}
                {c.adjudicator_id && ` · By: ${c.adjudicator_id}`}
              </div>
              {c.decision !== 'PENDING' ? (
                <div style={{ fontSize: 11, color: '#22c55e' }}>
                  ✓ {c.decision} {c.adjudication_notes ? `— ${c.adjudication_notes}` : ''}
                </div>
              ) : (
                <div>
                  <textarea
                    value={adjNotes[c.id] || ''}
                    onChange={(e) => setAdjNotes((prev) => ({ ...prev, [c.id]: e.target.value }))}
                    placeholder={lang === 'tr' ? 'Not (isteğe bağlı)…' : 'Note (optional)…'}
                    rows={2}
                    style={{ width: '100%', fontSize: 11, background: '#111827', color: '#d1d5db',
                             border: '1px solid #374151', borderRadius: 4, padding: '4px 6px',
                             resize: 'vertical', marginBottom: 6, boxSizing: 'border-box' }}
                  />
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {['KEEP_A', 'KEEP_B', 'KEEP_BOTH', 'EXCLUDE_BOTH'].map((d) => (
                      <button key={d} onClick={() => adjudicate(c.id, d)}
                        style={{ fontSize: 11, padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
                                 background: d === 'EXCLUDE_BOTH' ? '#7f1d1d' : '#1e3a5f',
                                 color: '#fff', border: 'none' }}>
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
          {!loadingConflicts && conflicts.length === 0 && (
            <div style={{ color: '#6b7280', fontSize: 12 }}>
              {lang === 'tr' ? 'Bu filtreyle çakışma bulunamadı.' : 'No conflicts match this filter.'}
            </div>
          )}
        </div>
      </section>

      {/* Export panel */}
      <section style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 14, color: '#e5e7eb', margin: '0 0 10px' }}>
          {lang === 'tr' ? 'Veri Seti Dışa Aktarımı (COCO/YOLO)' : 'Dataset Export (COCO/YOLO)'}
        </h2>
        <div style={{ background: '#1f2937', borderRadius: 8, padding: '14px 16px' }}>
          <div style={{ fontSize: 12, color: '#fbbf24', marginBottom: 10 }}>
            ⚠ {lang === 'tr'
              ? 'Sadece ONAYLANDI + ROI kırpılmış + işaret kaldırılmış annotasyonlar dahil edilir. Eğitim kapısı kapalıyken dışa aktarım devam edebilir ancak model eğitimine başlatamazsınız.'
              : 'Only APPROVED + ROI-cropped + markup-removed annotations are included. Export proceeds even with training gate closed, but you cannot start model training.'}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <input
              value={exportVersion}
              onChange={(e) => setExportVersion(e.target.value)}
              placeholder={lang === 'tr' ? 'Sürüm etiketi (ör. v1.0.0)' : 'Version tag (e.g. v1.0.0)'}
              style={{ flex: 1, fontSize: 12, background: '#111827', color: '#d1d5db',
                       border: '1px solid #374151', borderRadius: 4, padding: '6px 10px' }}
            />
            <button onClick={doExport} disabled={exporting}
              style={{ padding: '6px 14px', background: '#1d4ed8', color: '#fff',
                       border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
              {exporting ? (lang === 'tr' ? 'Dışa Aktarılıyor…' : 'Exporting…') :
                           (lang === 'tr' ? 'Dışa Aktar' : 'Export')}
            </button>
          </div>
          {exportResult && (
            <div style={{ fontSize: 12, color: '#d1d5db' }}>
              <div style={{ color: '#22c55e', marginBottom: 4 }}>
                ✓ {exportResult.coco_image_count as number} {lang === 'tr' ? 'görüntü,' : 'images,'}{' '}
                {exportResult.coco_annotation_count as number} {lang === 'tr' ? 'annotasyon' : 'annotations'}
              </div>
              {(exportResult.warnings as string[]).map((w, i) => (
                <div key={i} style={{ color: '#fbbf24', marginBottom: 2 }}>⚠ {w}</div>
              ))}
              {!exportResult.training_gate_open && (
                <div style={{ color: '#f87171', marginTop: 4, fontSize: 11 }}>
                  ✗ {lang === 'tr' ? 'Eğitim kapısı kapalı:' : 'Training gate closed:'}{' '}
                  {exportResult.training_blocked_reason as string}
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
