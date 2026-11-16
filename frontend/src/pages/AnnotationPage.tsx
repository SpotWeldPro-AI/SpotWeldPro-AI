/**
 * VISION-P3E: Human-in-the-Loop Weld Defect Annotation page.
 *
 * Layout:
 *   - Left panel: annotation list + filters
 *   - Centre: annotation canvas (zoom / pan / draw)
 *   - Right panel: defect selector + findings list + review panel
 *
 * Constraints enforced:
 *   - Original images are displayed read-only; not modified.
 *   - Self-approval blocked: submit and review by different users.
 *   - Training gate shown when blocked.
 *   - Multi-label: multiple findings per annotation.
 */
import { useState, useEffect, useCallback } from 'react'
import { AnnotationCanvas, Region, RegionType } from '../components/annotation/AnnotationCanvas'
import { useAppLanguage } from '../i18n/useAppLanguage'
import { getAuthHeaders } from '../api/client'
import { ModuleReadButton } from '../components/ModuleReadPanel'

const API = '/api/v1/annotation'

interface Annotation {
  id: number
  image_path: string
  roi_crop_path: string | null
  image_hash: string | null
  weld_id: string | null
  source_archive: string | null
  split: string
  label_provenance: string
  contamination_level: string
  max_markup_ratio: number
  is_roi_cropped: boolean
  annotation_markup_removed: boolean
  image_width_px: number | null
  image_height_px: number | null
  annotator_id: string
  review_status: string
  taxonomy_version: string
  export_eligible: boolean
  export_version: string | null
  created_at: string
  updated_at: string
  findings?: Finding[]
}

interface Finding {
  id: number
  defect_code: string
  name_tr: string
  name_en: string
  region_type: string
  region_data: Record<string, unknown>
  confidence: number
  confidence_source: string
  requires_physical_confirmation: boolean
  is_surface_classifiable: boolean
  created_at: string
}

type ToolMode = 'bbox' | 'polygon' | 'point' | 'pan' | 'select'

const STATUS_COLORS: Record<string, string> = {
  DRAFT: '#6b7280',
  SUBMITTED: '#3b82f6',
  APPROVED: '#22c55e',
  REJECTED: '#ef4444',
  NEEDS_REVISION: '#f59e0b',
}

const CONTAMINATION_COLORS: Record<string, string> = {
  CLEAN: '#22c55e',
  LOW: '#84cc16',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
  UNKNOWN: '#6b7280',
}

const TAXONOMY_CODES = [
  { code: 'ok',              tr: 'Kabul',                  en: 'Accepted' },
  { code: 'capak',           tr: 'Çapak',                  en: 'Spatter' },
  { code: 'deformeli',       tr: 'Deformeli',              en: 'Deformed' },
  { code: 'kopuk',           tr: 'Kopuk',                  en: 'Broken' },
  { code: 'eksik',           tr: 'Eksik',                  en: 'Missing' },
  { code: 'kucuk_cekirdek',  tr: 'Küçük Çekirdek',        en: 'Small Nugget Ind.' },
  { code: 'kacik',           tr: 'Kaçık',                  en: 'Misaligned' },
  { code: 'ust_uste',        tr: 'Üst Üste',               en: 'Overlapping' },
  { code: 'kenar',           tr: 'Kenar',                  en: 'Edge Weld' },
  { code: 'delik',           tr: 'Delik',                  en: 'Burn-Through' },
  { code: 'cift_sac',        tr: 'Çift Sac',               en: 'Double Sheet' },
  { code: 'cokertme',        tr: 'Çökürtme',               en: 'Crush Dent' },
  { code: 'generic_bad',     tr: 'Genel Hatalı (eski)',    en: 'Generic NOK (legacy)' },
  { code: 'expulsion',       tr: 'Pıskırma',               en: 'Expulsion' },
]

const REGION_TYPES: RegionType[] = ['BBOX', 'POLYGON', 'POINT', 'WHOLE_IMAGE']

export function AnnotationPage() {
  const { lang } = useAppLanguage()
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<Annotation | null>(null)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSplit, setFilterSplit] = useState('')
  const [filterContam, setFilterContam] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // canvas state
  const [regions, setRegions] = useState<Region[]>([])
  const [tool, setTool] = useState<ToolMode>('bbox')
  const [pendingCode, setPendingCode] = useState('capak')
  const [pendingRegionType, setPendingRegionType] = useState<RegionType>('BBOX')

  // review panel
  const [reviewNotes, setReviewNotes] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  const authHeaders = getAuthHeaders()

  async function fetchAnnotations() {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ limit: '50', offset: '0' })
      if (filterStatus) params.set('review_status', filterStatus)
      if (filterSplit) params.set('split', filterSplit)
      if (filterContam) params.set('contamination_level', filterContam)
      const res = await fetch(`${API}/?${params}`, { headers: authHeaders })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setAnnotations(data.items)
      setTotal(data.total)
    } catch (e) {
      setError(lang === 'tr' ? 'Annotasyonlar yüklenemedi.' : 'Failed to load annotations.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAnnotations() }, [filterStatus, filterSplit, filterContam])

  async function selectAnnotation(ann: Annotation) {
    try {
      const res = await fetch(`${API}/${ann.id}`, { headers: authHeaders })
      if (!res.ok) throw new Error()
      const full = await res.json()
      setSelected(full)
      // Build region list from findings
      const rs: Region[] = (full.findings || []).map((f: Finding) => ({
        id: String(f.id),
        type: f.region_type as RegionType,
        data: f.region_data,
        defectCode: f.defect_code,
      }))
      setRegions(rs)
    } catch {
      setError(lang === 'tr' ? 'Annotasyon detayı yüklenemedi.' : 'Failed to load annotation detail.')
    }
  }

  const handleRegionAdd = useCallback(async (r: Region) => {
    if (!selected) return
    if (selected.review_status !== 'DRAFT' && selected.review_status !== 'NEEDS_REVISION') return
    const code = TAXONOMY_CODES.find((c) => c.code === pendingCode) || TAXONOMY_CODES[1]
    try {
      const res = await fetch(`${API}/${selected.id}/finding`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          defect_code: pendingCode,
          name_tr: code.tr,
          name_en: code.en,
          region_type: pendingRegionType,
          region_data: r.data,
          confidence: 0,
          requires_physical_confirmation: ['kopuk', 'kucuk_cekirdek', 'cift_sac'].includes(pendingCode),
          is_surface_classifiable: !['incomplete_fusion', 'porosity', 'hot_crack', 'cold_lap'].includes(pendingCode),
        }),
      })
      if (!res.ok) throw new Error()
      const f: Finding = await res.json()
      setRegions((prev) => [...prev, {
        id: String(f.id), type: f.region_type as RegionType, data: f.region_data, defectCode: f.defect_code,
      }])
      setSelected((prev) => prev ? {
        ...prev, findings: [...(prev.findings || []), f]
      } : prev)
    } catch {
      setActionError(lang === 'tr' ? 'Bulgu eklenemedi.' : 'Failed to add finding.')
    }
  }, [selected, pendingCode, pendingRegionType, authHeaders, lang])

  async function removeFinding(annotationId: number, findingId: number) {
    try {
      const res = await fetch(`${API}/${annotationId}/finding/${findingId}`, {
        method: 'DELETE', headers: authHeaders,
      })
      if (!res.ok) throw new Error()
      setRegions((prev) => prev.filter((r) => r.id !== String(findingId)))
      setSelected((prev) => prev ? {
        ...prev, findings: (prev.findings || []).filter((f) => f.id !== findingId)
      } : prev)
    } catch {
      setActionError(lang === 'tr' ? 'Bulgu silinemedi.' : 'Failed to remove finding.')
    }
  }

  async function doSubmit() {
    if (!selected) return
    setActionLoading(true); setActionError(''); setActionSuccess('')
    try {
      const res = await fetch(`${API}/${selected.id}/submit`, {
        method: 'PATCH', headers: authHeaders,
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error') }
      const updated = await res.json()
      setSelected(updated)
      setAnnotations((prev) => prev.map((a) => a.id === updated.id ? { ...a, review_status: updated.review_status } : a))
      setActionSuccess(lang === 'tr' ? 'İncelemeye gönderildi.' : 'Submitted for review.')
    } catch (e: unknown) {
      setActionError(String(e instanceof Error ? e.message : e))
    } finally { setActionLoading(false) }
  }

  async function doReview(decision: string) {
    if (!selected) return
    setActionLoading(true); setActionError(''); setActionSuccess('')
    try {
      const res = await fetch(`${API}/${selected.id}/review`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, notes: reviewNotes }),
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error') }
      const updated = await res.json()
      setSelected(updated)
      setAnnotations((prev) => prev.map((a) => a.id === updated.id ? { ...a, review_status: updated.review_status } : a))
      setActionSuccess(lang === 'tr' ? 'İnceleme kaydedildi.' : 'Review saved.')
      setReviewNotes('')
    } catch (e: unknown) {
      setActionError(String(e instanceof Error ? e.message : e))
    } finally { setActionLoading(false) }
  }

  async function doReopen() {
    if (!selected) return
    setActionLoading(true); setActionError(''); setActionSuccess('')
    try {
      const res = await fetch(`${API}/${selected.id}/reopen`, {
        method: 'POST', headers: authHeaders,
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error') }
      const updated = await res.json()
      setSelected(updated)
      setAnnotations((prev) => prev.map((a) => a.id === updated.id ? { ...a, review_status: updated.review_status } : a))
      setActionSuccess(lang === 'tr' ? 'Yeniden açıldı.' : 'Reopened.')
    } catch (e: unknown) {
      setActionError(String(e instanceof Error ? e.message : e))
    } finally { setActionLoading(false) }
  }

  const imgW = selected?.image_width_px || 640
  const imgH = selected?.image_height_px || 480
  const imgSrc = selected
    ? `/api/v1/annotation/image-proxy?path=${encodeURIComponent(selected.roi_crop_path || selected.image_path)}`
    : ''
  const editable = selected?.review_status === 'DRAFT' || selected?.review_status === 'NEEDS_REVISION'

  return (
    <div style={{ display: 'flex', height: '100%', gap: 0, minHeight: 0 }}>

      {/* Left: list panel */}
      <aside style={{ width: 260, flexShrink: 0, borderRight: '1px solid #333',
                      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '12px 12px 8px', borderBottom: '1px solid #333' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <h2 style={{ margin: 0, fontSize: 14, color: '#e5e7eb', flex: 1 }}>
              {lang === 'tr' ? 'Annotasyonlar' : 'Annotations'} ({total})
            </h2>
            <ModuleReadButton moduleId="annotation" />
          </div>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
            style={{ width: '100%', marginBottom: 4, fontSize: 12, background: '#1f2937', color: '#d1d5db', border: '1px solid #374151', borderRadius: 4, padding: '3px 6px' }}>
            <option value="">— {lang === 'tr' ? 'Tüm Durumlar' : 'All Statuses'} —</option>
            {['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'NEEDS_REVISION'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select value={filterSplit} onChange={(e) => setFilterSplit(e.target.value)}
            style={{ width: '100%', marginBottom: 4, fontSize: 12, background: '#1f2937', color: '#d1d5db', border: '1px solid #374151', borderRadius: 4, padding: '3px 6px' }}>
            <option value="">— {lang === 'tr' ? 'Tüm Bölünmeler' : 'All Splits'} —</option>
            {['train', 'val', 'test', 'unknown'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select value={filterContam} onChange={(e) => setFilterContam(e.target.value)}
            style={{ width: '100%', fontSize: 12, background: '#1f2937', color: '#d1d5db', border: '1px solid #374151', borderRadius: 4, padding: '3px 6px' }}>
            <option value="">— {lang === 'tr' ? 'Tüm Kirlilik' : 'All Contamination'} —</option>
            {['CLEAN', 'LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        {error && <div style={{ padding: 8, color: '#f87171', fontSize: 12 }}>{error}</div>}
        {loading && <div style={{ padding: 8, color: '#9ca3af', fontSize: 12 }}>
          {lang === 'tr' ? 'Yükleniyor…' : 'Loading…'}
        </div>}
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {annotations.map((ann) => (
            <button
              key={ann.id}
              onClick={() => selectAnnotation(ann)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', background: selected?.id === ann.id ? '#1e40af22' : 'transparent',
                border: 'none', borderBottom: '1px solid #1f2937', cursor: 'pointer',
                color: '#d1d5db',
              }}
            >
              <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 2 }}>#{ann.id}</div>
              <div style={{ fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {ann.image_path.split(/[\\/]/).pop()}
              </div>
              <div style={{ display: 'flex', gap: 4, marginTop: 3, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 10, background: STATUS_COLORS[ann.review_status] + '33',
                               color: STATUS_COLORS[ann.review_status], borderRadius: 3, padding: '1px 4px' }}>
                  {ann.review_status}
                </span>
                <span style={{ fontSize: 10, background: CONTAMINATION_COLORS[ann.contamination_level] + '22',
                               color: CONTAMINATION_COLORS[ann.contamination_level], borderRadius: 3, padding: '1px 4px' }}>
                  {ann.contamination_level}
                </span>
                <span style={{ fontSize: 10, color: '#6b7280' }}>{ann.split}</span>
              </div>
            </button>
          ))}
          {!loading && annotations.length === 0 && (
            <div style={{ padding: 16, color: '#6b7280', fontSize: 12, textAlign: 'center' }}>
              {lang === 'tr' ? 'Kayıt bulunamadı.' : 'No records found.'}
            </div>
          )}
        </div>
      </aside>

      {/* Centre: canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0 }}>
        {/* Tool bar */}
        <div style={{ padding: '6px 12px', background: '#111827', borderBottom: '1px solid #333',
                      display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          {(['bbox', 'polygon', 'point', 'pan', 'select'] as ToolMode[]).map((t) => (
            <button key={t} onClick={() => setTool(t)} style={{
              padding: '3px 10px', fontSize: 12, borderRadius: 4,
              background: tool === t ? '#1d4ed8' : '#1f2937',
              color: tool === t ? '#fff' : '#9ca3af',
              border: '1px solid ' + (tool === t ? '#3b82f6' : '#374151'), cursor: 'pointer',
            }}>{t.toUpperCase()}</button>
          ))}
          <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 8 }}>
            {lang === 'tr' ? 'Yakınlaştır: Tekerlek | Kaydır: Boşluk+sürükle' : 'Zoom: Wheel | Pan: Space+drag'}
          </span>
        </div>
        {/* Canvas */}
        <div style={{ flex: 1, minHeight: 0 }}>
          {selected ? (
            <AnnotationCanvas
              imageSrc={imgSrc}
              imageWidth={imgW}
              imageHeight={imgH}
              regions={regions}
              activeTool={tool}
              onRegionAdd={editable ? handleRegionAdd : undefined}
              readOnly={!editable}
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                          height: '100%', color: '#6b7280', fontSize: 14 }}>
              {lang === 'tr' ? 'Soldan bir annotasyon seçin.' : 'Select an annotation from the left.'}
            </div>
          )}
        </div>
      </div>

      {/* Right: defect selector + findings + review */}
      <aside style={{ width: 280, flexShrink: 0, borderLeft: '1px solid #333',
                      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {selected ? (
          <>
            {/* Defect selector */}
            <div style={{ padding: '10px 12px', borderBottom: '1px solid #333' }}>
              <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>
                {lang === 'tr' ? 'Hata Kodu' : 'Defect Code'}
              </div>
              <select value={pendingCode} onChange={(e) => setPendingCode(e.target.value)}
                disabled={!editable}
                style={{ width: '100%', marginBottom: 6, fontSize: 12, background: '#1f2937',
                         color: '#d1d5db', border: '1px solid #374151', borderRadius: 4, padding: '4px 6px' }}>
                {TAXONOMY_CODES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {lang === 'tr' ? `${c.tr} (${c.code})` : `${c.en} (${c.code})`}
                  </option>
                ))}
              </select>
              <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 4 }}>
                {lang === 'tr' ? 'Bölge Türü' : 'Region Type'}
              </div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {REGION_TYPES.map((rt) => (
                  <button key={rt} onClick={() => setPendingRegionType(rt)} disabled={!editable}
                    style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                             background: pendingRegionType === rt ? '#1d4ed8' : '#1f2937',
                             color: pendingRegionType === rt ? '#fff' : '#9ca3af',
                             border: '1px solid ' + (pendingRegionType === rt ? '#3b82f6' : '#374151') }}>
                    {rt}
                  </button>
                ))}
              </div>
            </div>

            {/* Findings list */}
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #333',
                          overflowY: 'auto', maxHeight: 200 }}>
              <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>
                {lang === 'tr' ? 'Bulgular' : 'Findings'} ({(selected.findings || []).length})
              </div>
              {(selected.findings || []).length === 0 && (
                <div style={{ fontSize: 11, color: '#6b7280' }}>
                  {lang === 'tr' ? 'Henüz bulgu yok.' : 'No findings yet.'}
                </div>
              )}
              {(selected.findings || []).map((f) => (
                <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 6,
                                         marginBottom: 4, padding: '4px 6px', background: '#1f2937',
                                         borderRadius: 4 }}>
                  <span style={{ flex: 1, fontSize: 11, color: '#d1d5db' }}>
                    {lang === 'tr' ? f.name_tr : f.name_en}
                    <span style={{ color: '#6b7280', marginLeft: 4 }}>[{f.region_type}]</span>
                  </span>
                  {editable && (
                    <button onClick={() => removeFinding(selected.id, f.id)}
                      style={{ fontSize: 10, color: '#f87171', background: 'none', border: 'none',
                               cursor: 'pointer', padding: '1px 4px' }}>✕</button>
                  )}
                </div>
              ))}
            </div>

            {/* Status + metadata */}
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #333' }}>
              <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>
                {lang === 'tr' ? 'Durum:' : 'Status:'}
                <span style={{ marginLeft: 6, color: STATUS_COLORS[selected.review_status] || '#fff',
                               fontWeight: 600 }}>
                  {selected.review_status}
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#6b7280' }}>
                {lang === 'tr' ? 'Kirlilik:' : 'Contamination:'}
                <span style={{ marginLeft: 4, color: CONTAMINATION_COLORS[selected.contamination_level] }}>
                  {selected.contamination_level}
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#6b7280' }}>
                {lang === 'tr' ? 'Kaynak:' : 'Archive:'} {selected.source_archive || '—'}
              </div>
              <div style={{ fontSize: 11, color: '#6b7280' }}>
                {lang === 'tr' ? 'Bölünme:' : 'Split:'} {selected.split}
              </div>
              {selected.export_eligible && (
                <div style={{ fontSize: 11, color: '#22c55e', marginTop: 4 }}>
                  ✓ {lang === 'tr' ? 'Dışa aktarıma uygun' : 'Export eligible'}
                </div>
              )}
            </div>

            {/* Review panel */}
            <div style={{ padding: '8px 12px', flex: 1, overflowY: 'auto' }}>
              <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>
                {lang === 'tr' ? 'İnceleme İşlemleri' : 'Review Actions'}
              </div>

              {actionError && (
                <div style={{ fontSize: 11, color: '#f87171', marginBottom: 6 }}>{actionError}</div>
              )}
              {actionSuccess && (
                <div style={{ fontSize: 11, color: '#22c55e', marginBottom: 6 }}>{actionSuccess}</div>
              )}

              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder={lang === 'tr' ? 'İnceleme notu (isteğe bağlı)…' : 'Review notes (optional)…'}
                rows={3}
                style={{ width: '100%', fontSize: 12, background: '#1f2937', color: '#d1d5db',
                         border: '1px solid #374151', borderRadius: 4, padding: '6px 8px',
                         resize: 'vertical', marginBottom: 8, boxSizing: 'border-box' }}
              />

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {selected.review_status === 'DRAFT' && (
                  <button onClick={doSubmit} disabled={actionLoading}
                    style={{ padding: '6px 12px', background: '#1d4ed8', color: '#fff',
                             border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                    {lang === 'tr' ? 'İncelemeye Gönder' : 'Submit for Review'}
                  </button>
                )}
                {selected.review_status === 'SUBMITTED' && (
                  <>
                    <button onClick={() => doReview('approve')} disabled={actionLoading}
                      style={{ padding: '6px 12px', background: '#16a34a', color: '#fff',
                               border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                      {lang === 'tr' ? 'Onayla' : 'Approve'}
                    </button>
                    <button onClick={() => doReview('request_revision')} disabled={actionLoading}
                      style={{ padding: '6px 12px', background: '#b45309', color: '#fff',
                               border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                      {lang === 'tr' ? 'Revizyon İste' : 'Request Revision'}
                    </button>
                    <button onClick={() => doReview('reject')} disabled={actionLoading}
                      style={{ padding: '6px 12px', background: '#7f1d1d', color: '#fff',
                               border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                      {lang === 'tr' ? 'Reddet' : 'Reject'}
                    </button>
                  </>
                )}
                {(selected.review_status === 'NEEDS_REVISION' || selected.review_status === 'REJECTED') && (
                  <button onClick={doReopen} disabled={actionLoading}
                    style={{ padding: '6px 12px', background: '#374151', color: '#d1d5db',
                             border: '1px solid #4b5563', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                    {lang === 'tr' ? 'Yeniden Aç' : 'Reopen'}
                  </button>
                )}
                {selected.review_status === 'APPROVED' && (
                  <div style={{ fontSize: 11, color: '#22c55e', textAlign: 'center' }}>
                    ✓ {lang === 'tr' ? 'Onaylandı' : 'Approved'}
                  </div>
                )}
              </div>

              {/* Training gate warning */}
              <div style={{ marginTop: 12, padding: '8px 10px', background: '#78350f22',
                            border: '1px solid #78350f', borderRadius: 4, fontSize: 11, color: '#fbbf24' }}>
                ⚠ {lang === 'tr'
                  ? 'Eğitim kapısı kapalı. E1–E4 kapıları çözümlenene kadar model eğitimi yapılamaz.'
                  : 'Training gate closed. Model training blocked until gates E1–E4 are resolved.'}
              </div>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', color: '#6b7280', fontSize: 13, padding: 16, textAlign: 'center' }}>
            {lang === 'tr' ? 'İncelemek için bir annotasyon seçin.' : 'Select an annotation to review.'}
          </div>
        )}
      </aside>
    </div>
  )
}
