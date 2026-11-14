/**
 * VISION-P3I: Side-by-side conflict review queue for label-conflict duplicate pairs.
 *
 * Shows:
 *  - Prioritized queue: BOTH (critical) → LABEL_CONFLICT → CROSS_SPLIT_LEAKAGE
 *  - Side-by-side: image path, label TR/EN, split, source archive, contamination, SHA1
 *  - Five reviewer decisions with required notes
 *  - Review progress bar and summary
 *  - Role guard: PROCESS_ENGINEER, QUALITY_ENGINEER, SYSTEM_ADMIN only
 *
 * Hard rules enforced:
 *  - Notes required for every decision (enforced server-side and client-side)
 *  - Original labels displayed but never automatically changed
 *  - No auto-adjudication
 *  - Training gate indicator always shown
 */
import { useState, useEffect, useCallback } from 'react'
import { useAppLanguage } from '../i18n/useAppLanguage'
import { getAuthHeaders } from '../api/client'

const API = '/api/v1/annotation'

const TAXONOMY: Record<string, { tr: string; en: string }> = {
  ok:             { tr: 'Kabul',           en: 'Accepted' },
  capak:          { tr: 'Çapak',           en: 'Spatter' },
  deformeli:      { tr: 'Deformeli',       en: 'Deformed' },
  kopuk:          { tr: 'Kopuk',           en: 'Broken' },
  eksik:          { tr: 'Eksik',           en: 'Missing' },
  kucuk_cekirdek: { tr: 'Küçük Çekirdek', en: 'Small Nugget Ind.' },
  kacik:          { tr: 'Kaçık',          en: 'Misaligned' },
  ust_uste:       { tr: 'Üst Üste',       en: 'Overlapping' },
  kenar:          { tr: 'Kenar',          en: 'Edge Weld' },
  delik:          { tr: 'Delik',          en: 'Burn-Through' },
  cift_sac:       { tr: 'Çift Sac',       en: 'Double Sheet' },
  cokertme:       { tr: 'Çökürtme',       en: 'Crush Dent' },
  generic_bad:    { tr: 'Genel Hatalı (eski)', en: 'Generic NOK (legacy)' },
  expulsion:      { tr: 'Pıskırma',        en: 'Expulsion' },
}

const PRIORITY: Record<string, number> = { BOTH: 0, LABEL_CONFLICT: 1, CROSS_SPLIT_LEAKAGE: 2 }

const DECISIONS = [
  {
    value: 'CONFIRM_LABEL',
    label_tr: 'Etiketi Onayla',
    label_en: 'Confirm Label',
    desc_en: 'Both labels are consistent; keep the more specific one.',
    color: '#22c55e',
  },
  {
    value: 'CORRECT_LABEL',
    label_tr: 'Etiketi Düzelt',
    label_en: 'Correct Label',
    desc_en: 'One label is wrong; specify the correct label in notes.',
    color: '#3b82f6',
  },
  {
    value: 'EXCLUDE_FROM_TRAINING',
    label_tr: 'Eğitimden Hariç Tut',
    label_en: 'Exclude from Training',
    desc_en: 'Exclude both paths from training; keep in DB.',
    color: '#f59e0b',
  },
  {
    value: 'INSUFFICIENT_EVIDENCE',
    label_tr: 'Yetersiz Kanıt',
    label_en: 'Insufficient Evidence',
    desc_en: 'Cannot determine correct label without more data.',
    color: '#a78bfa',
  },
  {
    value: 'NEEDS_PHYSICAL_TEST',
    label_tr: 'Fiziksel Test Gerekli',
    label_en: 'Needs Physical Test',
    desc_en: 'Destructive test required before label can be confirmed.',
    color: '#ef4444',
  },
]

const CONFLICT_PRIORITY_LABELS: Record<string, { badge: string; color: string }> = {
  BOTH:               { badge: 'CRITICAL', color: '#ef4444' },
  LABEL_CONFLICT:     { badge: 'HIGH',     color: '#f59e0b' },
  CROSS_SPLIT_LEAKAGE:{ badge: 'MEDIUM',   color: '#a78bfa' },
}

const CONTAM_COLORS: Record<string, string> = {
  CLEAN: '#22c55e', LOW: '#84cc16', MEDIUM: '#f59e0b', HIGH: '#ef4444', UNKNOWN: '#6b7280',
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

interface ReviewSummary {
  total: number
  pending: number
  resolved: number
  e1_gate_clear: boolean
  by_decision: Record<string, number>
  by_conflict_type: Record<string, number>
  needs_physical_test: number
  insufficient_evidence: number
  completion_pct: number
}

interface EligibleCounts {
  total_records: number
  total_clean_low: number
  training_eligible: number
  eval_eligible: number
  excluded_paths_count: number
  pending_conflict_paths_count: number
  surface_classifier_go: boolean
}

function labelDisplay(code: string, lang: string): string {
  const t = TAXONOMY[code]
  if (!t) return code
  return lang === 'tr' ? `${t.tr} (${code})` : `${t.en} (${code})`
}

function basename(p: string): string {
  return p.replace(/\\/g, '/').split('/').pop() || p
}

function ImagePanel({ path, label, split, archive, sha1, contam, side, lang }:
  { path: string; label: string; split: string; archive: string; sha1: string; contam?: string; side: 'A' | 'B'; lang: string }) {
  return (
    <div style={{ flex: 1, background: '#111827', borderRadius: 10, padding: 16, border: '1px solid #374151', minWidth: 0 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', marginBottom: 8 }}>
        {lang === 'tr' ? `Görüntü ${side}` : `Image ${side}`}
      </div>

      {/* Image placeholder — real images displayed only when paths are accessible */}
      <div style={{ background: '#1f2937', borderRadius: 6, height: 180, display: 'flex',
                    alignItems: 'center', justifyContent: 'center', marginBottom: 12,
                    border: '1px dashed #374151', overflow: 'hidden' }}>
        <img
          src={`/api/v1/annotation/image-preview?path=${encodeURIComponent(path)}`}
          alt={basename(path)}
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
        />
        <span style={{ fontSize: 11, color: '#4b5563', position: 'absolute' }}>{basename(path)}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', fontSize: 11 }}>
        <Field label={lang === 'tr' ? 'Etiket' : 'Label'} value={labelDisplay(label, lang)} highlight />
        <Field label={lang === 'tr' ? 'Bölüm' : 'Split'} value={split} />
        <Field label={lang === 'tr' ? 'Kaynak' : 'Archive'} value={archive} />
        <Field label="SHA1" value={sha1.slice(0, 12) + '…'} mono />
        {contam && (
          <Field label={lang === 'tr' ? 'Kirlilik' : 'Contamination'} value={contam}
            color={CONTAM_COLORS[contam] || '#6b7280'} />
        )}
      </div>
      <div style={{ marginTop: 8, fontSize: 10, color: '#6b7280', wordBreak: 'break-all' }}>{path}</div>
    </div>
  )
}

function Field({ label, value, highlight, mono, color }:
  { label: string; value: string; highlight?: boolean; mono?: boolean; color?: string }) {
  return (
    <div>
      <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 1 }}>{label}</div>
      <div style={{
        fontFamily: mono ? 'monospace' : undefined,
        color: color || (highlight ? '#f9fafb' : '#d1d5db'),
        fontWeight: highlight ? 600 : undefined,
        fontSize: 11,
      }}>{value}</div>
    </div>
  )
}

export function ConflictReviewPage() {
  const { lang } = useAppLanguage()
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [summary, setSummary] = useState<ReviewSummary | null>(null)
  const [eligibleCounts, setEligibleCounts] = useState<EligibleCounts | null>(null)
  const [filterDecision, setFilterDecision] = useState('PENDING')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [notes, setNotes] = useState('')
  const [chosenDecision, setChosenDecision] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [loadingConflicts, setLoadingConflicts] = useState(false)

  const authHeaders = getAuthHeaders()

  const fetchConflicts = useCallback(async () => {
    setLoadingConflicts(true)
    setError('')
    try {
      const params = new URLSearchParams({ limit: '200', offset: '0' })
      if (filterDecision) params.set('decision', filterDecision)
      const res = await fetch(`${API}/conflicts?${params}`, { headers: authHeaders })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      // Sort by priority: BOTH first, then LABEL_CONFLICT, then CROSS_SPLIT_LEAKAGE
      const sorted = (data.items as Conflict[]).sort((a, b) =>
        (PRIORITY[a.conflict_type] ?? 9) - (PRIORITY[b.conflict_type] ?? 9)
      )
      setConflicts(sorted)
    } catch {
      setError(lang === 'tr' ? 'Çakışmalar yüklenemedi.' : 'Failed to load conflicts.')
    } finally { setLoadingConflicts(false) }
  }, [filterDecision, lang])

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/conflicts/review-summary`, { headers: authHeaders })
      if (res.ok) setSummary(await res.json())
    } catch { /* summary is optional */ }
  }, [])

  const fetchEligibleCounts = useCallback(async () => {
    try {
      const res = await fetch(`${API}/conflicts/eligible-counts`, { headers: authHeaders })
      if (res.ok) setEligibleCounts(await res.json())
    } catch { /* optional */ }
  }, [])

  useEffect(() => {
    fetchConflicts()
    fetchSummary()
    fetchEligibleCounts()
  }, [fetchConflicts, fetchSummary, fetchEligibleCounts])

  const selectedConflict = conflicts.find(c => c.id === selectedId) ?? null

  async function submitDecision() {
    if (!selectedId || !chosenDecision) {
      setError(lang === 'tr' ? 'Karar seçiniz.' : 'Choose a decision.'); return
    }
    if (!notes.trim()) {
      setError(lang === 'tr' ? 'Notlar zorunludur.' : 'Reviewer notes are required.'); return
    }
    setSubmitting(true); setError('')
    try {
      const res = await fetch(`${API}/conflicts/${selectedId}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: chosenDecision, notes: notes.trim() }),
      })
      if (!res.ok) {
        const e = await res.json()
        throw new Error(e.detail || `HTTP ${res.status}`)
      }
      setNotes(''); setChosenDecision(''); setSelectedId(null)
      await Promise.all([fetchConflicts(), fetchSummary(), fetchEligibleCounts()])
    } catch (e: unknown) {
      setError(String(e instanceof Error ? e.message : e))
    } finally { setSubmitting(false) }
  }

  const pct = summary ? summary.completion_pct : 0
  const isE1Clear = summary?.e1_gate_clear ?? false

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif', color: '#f9fafb',
                  maxWidth: 1400, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>
          {lang === 'tr' ? 'Çakışma İnceleme Kuyruğu' : 'Conflict Review Queue'}
        </h1>
        <p style={{ margin: '4px 0 0', color: '#9ca3af', fontSize: 13 }}>
          {lang === 'tr'
            ? 'P3I — Etiket çakışmaları insan incelemesiyle çözülür. Otomatik karar verilmez.'
            : 'P3I — Label conflicts resolved by human review. No automatic adjudication.'}
        </p>
      </div>

      {/* Training gate + progress */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px', background: isE1Clear ? '#14532d22' : '#7f1d1d22',
                      border: '1px solid ' + (isE1Clear ? '#16a34a' : '#dc2626'),
                      borderRadius: 8, padding: '10px 14px' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: isE1Clear ? '#86efac' : '#fca5a5' }}>
            {isE1Clear ? '✓ ' : '✗ '}E1 Gate — {lang === 'tr' ? 'Çakışma Çözümü' : 'Conflict Resolution'}
          </div>
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
            {lang === 'tr'
              ? (isE1Clear ? 'Tüm çakışmalar çözüldü.' : 'Bekleyen çakışmalar eğitimi engelliyor.')
              : (isE1Clear ? 'All conflicts resolved.' : 'Pending conflicts block training.')}
          </div>
        </div>

        {summary && (
          <div style={{ flex: '1 1 240px', background: '#1f2937', borderRadius: 8, padding: '10px 14px',
                        border: '1px solid #374151' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#d1d5db', marginBottom: 6 }}>
              {lang === 'tr' ? 'İlerleme' : 'Progress'} — {summary.resolved}/{summary.total} ({pct}%)
            </div>
            <div style={{ background: '#374151', borderRadius: 4, height: 6, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: pct === 100 ? '#22c55e' : '#3b82f6',
                            transition: 'width 0.3s' }} />
            </div>
            <div style={{ marginTop: 6, fontSize: 11, color: '#6b7280' }}>
              {lang === 'tr' ? `${summary.pending} bekliyor` : `${summary.pending} pending`}
              {summary.needs_physical_test > 0 && ` · ${summary.needs_physical_test} ${lang === 'tr' ? 'fiziksel test' : 'need physical test'}`}
              {summary.insufficient_evidence > 0 && ` · ${summary.insufficient_evidence} ${lang === 'tr' ? 'yetersiz kanıt' : 'insufficient evidence'}`}
            </div>
          </div>
        )}

        {eligibleCounts && (
          <div style={{ flex: '1 1 240px', background: eligibleCounts.surface_classifier_go ? '#14532d22' : '#1f2937',
                        borderRadius: 8, padding: '10px 14px',
                        border: '1px solid ' + (eligibleCounts.surface_classifier_go ? '#16a34a' : '#374151') }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#d1d5db', marginBottom: 4 }}>
              {lang === 'tr' ? 'Uygun Örnekler' : 'Eligible Samples'}
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af' }}>
              {lang === 'tr' ? 'Eğitim' : 'Train'}: <b style={{ color: '#f9fafb' }}>{eligibleCounts.training_eligible}</b>
              {' / 200 min · '}
              {lang === 'tr' ? 'Test' : 'Test'}: <b style={{ color: '#f9fafb' }}>{eligibleCounts.eval_eligible}</b>
              {' / 40 min'}
            </div>
            <div style={{ marginTop: 4, fontSize: 10, color: eligibleCounts.surface_classifier_go ? '#86efac' : '#6b7280' }}>
              {lang === 'tr' ? 'Yüzey sınıflandırıcı' : 'Surface classifier'}:
              {' '}{eligibleCounts.surface_classifier_go
                ? (lang === 'tr' ? 'ŞARTLI GEÇ' : 'CONDITIONAL GO')
                : (lang === 'tr' ? 'HAYIR-GEÇ' : 'NO-GO')}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', border: '1px solid #dc2626', borderRadius: 6,
                      padding: '8px 14px', marginBottom: 16, fontSize: 13, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20 }}>

        {/* Queue panel */}
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            {['PENDING', '', 'NEEDS_PHYSICAL_TEST', 'INSUFFICIENT_EVIDENCE'].map(d => (
              <button key={d || 'all'} onClick={() => setFilterDecision(d)}
                style={{ flex: 1, padding: '5px 4px', fontSize: 10, borderRadius: 5, cursor: 'pointer',
                         background: filterDecision === d ? '#3b82f6' : '#1f2937',
                         color: '#f9fafb', border: '1px solid #374151' }}>
                {d === 'PENDING' ? (lang === 'tr' ? 'Bekliyor' : 'Pending')
                  : d === '' ? (lang === 'tr' ? 'Tümü' : 'All')
                  : d === 'NEEDS_PHYSICAL_TEST' ? (lang === 'tr' ? 'Fiziksel' : 'Physical')
                  : (lang === 'tr' ? 'Kanıtsız' : 'No Evid.')}
              </button>
            ))}
          </div>

          {loadingConflicts ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>
              {lang === 'tr' ? 'Yükleniyor…' : 'Loading…'}
            </div>
          ) : conflicts.length === 0 ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>
              {lang === 'tr' ? 'Kayıt bulunamadı.' : 'No conflicts found.'}
            </div>
          ) : (
            <div style={{ maxHeight: 600, overflowY: 'auto' }}>
              {conflicts.map(c => {
                const pri = CONFLICT_PRIORITY_LABELS[c.conflict_type]
                const isSelected = c.id === selectedId
                return (
                  <div key={c.id} onClick={() => { setSelectedId(c.id); setNotes(''); setChosenDecision('') }}
                    style={{ cursor: 'pointer', padding: '10px 12px', marginBottom: 6, borderRadius: 8,
                             background: isSelected ? '#1e3a5f' : '#1f2937',
                             border: `1px solid ${isSelected ? '#3b82f6' : '#374151'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 10, fontWeight: 700, color: pri?.color || '#9ca3af',
                                     background: (pri?.color || '#9ca3af') + '22',
                                     padding: '1px 6px', borderRadius: 4 }}>
                        {pri?.badge || c.conflict_type}
                      </span>
                      <span style={{ fontSize: 10, color: c.decision === 'PENDING' ? '#f59e0b' : '#22c55e' }}>
                        {c.decision}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: '#d1d5db' }}>
                      <b style={{ color: '#fbbf24' }}>{labelDisplay(c.label_a, lang)}</b>
                      {' vs '}
                      <b style={{ color: '#60a5fa' }}>{labelDisplay(c.label_b, lang)}</b>
                    </div>
                    <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                      {c.split_a} / {c.split_b} · {c.sha1_16.slice(0, 10)}…
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Detail + decision panel */}
        <div>
          {!selectedConflict ? (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 40, textAlign: 'center',
                          border: '1px solid #374151', color: '#6b7280', fontSize: 14 }}>
              {lang === 'tr'
                ? '← Sol taraftan incelenecek bir çakışma seçin.'
                : '← Select a conflict from the queue to review.'}
            </div>
          ) : (
            <>
              {/* Side-by-side images */}
              <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <ImagePanel
                  path={selectedConflict.path_a} label={selectedConflict.label_a}
                  split={selectedConflict.split_a} archive={selectedConflict.source_archive_a}
                  sha1={selectedConflict.sha1_16} side="A" lang={lang}
                />
                <ImagePanel
                  path={selectedConflict.path_b} label={selectedConflict.label_b}
                  split={selectedConflict.split_b} archive={selectedConflict.source_archive_b}
                  sha1={selectedConflict.sha1_16} side="B" lang={lang}
                />
              </div>

              {/* Decision panel */}
              {selectedConflict.decision === 'PENDING' ? (
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 20,
                              border: '1px solid #374151' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 14 }}>
                    {lang === 'tr' ? 'İnceleme Kararı' : 'Reviewer Decision'}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                                gap: 8, marginBottom: 16 }}>
                    {DECISIONS.map(d => (
                      <button key={d.value} onClick={() => setChosenDecision(d.value)}
                        style={{ padding: '10px 12px', borderRadius: 8, cursor: 'pointer', textAlign: 'left',
                                 background: chosenDecision === d.value ? d.color + '33' : '#111827',
                                 border: `2px solid ${chosenDecision === d.value ? d.color : '#374151'}`,
                                 color: '#f9fafb' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: d.color, marginBottom: 3 }}>
                          {lang === 'tr' ? d.label_tr : d.label_en}
                        </div>
                        <div style={{ fontSize: 10, color: '#9ca3af' }}>{d.desc_en}</div>
                      </button>
                    ))}
                  </div>

                  <textarea
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder={lang === 'tr'
                      ? 'İnceleme notları (zorunlu)…'
                      : 'Reviewer notes (required)…'}
                    rows={3}
                    style={{ width: '100%', boxSizing: 'border-box', background: '#111827',
                             color: '#f9fafb', border: '1px solid #374151', borderRadius: 6,
                             padding: '8px 10px', fontSize: 12, resize: 'vertical', marginBottom: 12 }}
                  />

                  <button
                    onClick={submitDecision}
                    disabled={submitting || !chosenDecision || !notes.trim()}
                    style={{ padding: '8px 24px', borderRadius: 6, cursor: 'pointer', fontSize: 13,
                             background: (!chosenDecision || !notes.trim()) ? '#374151' : '#3b82f6',
                             color: '#f9fafb', border: 'none', fontWeight: 600 }}>
                    {submitting
                      ? (lang === 'tr' ? 'Kaydediliyor…' : 'Saving…')
                      : (lang === 'tr' ? 'Kararı Kaydet' : 'Save Decision')}
                  </button>
                </div>
              ) : (
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 20,
                              border: '1px solid #374151' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#22c55e', marginBottom: 8 }}>
                    ✓ {lang === 'tr' ? 'Karar Kaydedildi' : 'Decision Recorded'}
                  </div>
                  <div style={{ fontSize: 12, color: '#d1d5db' }}>
                    <b>{lang === 'tr' ? 'Karar:' : 'Decision:'}</b> {selectedConflict.decision}
                  </div>
                  <div style={{ fontSize: 12, color: '#d1d5db', marginTop: 4 }}>
                    <b>{lang === 'tr' ? 'İnceleyici:' : 'Reviewer:'}</b> {selectedConflict.adjudicator_id}
                  </div>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
                    {selectedConflict.adjudication_notes}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
