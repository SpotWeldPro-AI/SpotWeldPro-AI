/**
 * VISION-DATA-REAL-02 E4: Physical Test Evidence entry and review.
 *
 * Rules enforced:
 *  - SURFACE_OBSERVATION is not a valid test method here (use annotation workflow instead)
 *  - Nugget measurements require CROSS_SECTION or UT_SCAN
 *  - VERIFIED evidence quality requires a report reference number
 *  - Only PROCESS_ENGINEER, QUALITY_ENGINEER, SYSTEM_ADMIN can submit evidence
 *  - No automatic training gate changes occur from this page
 *  - Original images are never modified
 */
import { useState, useEffect, useCallback } from 'react'
import { useAppLanguage } from '../i18n/useAppLanguage'
import { getAuthHeaders } from '../api/client'
import { ModuleReadButton } from '../components/ModuleReadPanel'

const API = '/api/v1/annotation'

const TEST_METHODS = [
  { value: 'CROSS_SECTION', label_en: 'Cross-Section (Metallographic)', label_tr: 'Kesit (Metalografik)', nugget: true },
  { value: 'PEEL_TEST',     label_en: 'Peel Test',                     label_tr: 'Soyma Testi',          nugget: false },
  { value: 'CHISEL_TEST',   label_en: 'Chisel Test',                   label_tr: 'Keski Testi',           nugget: false },
  { value: 'UT_SCAN',       label_en: 'Ultrasonic (UT/NDT)',           label_tr: 'Ultrasonik (UT/NDT)',   nugget: true },
  { value: 'XRF',           label_en: 'X-Ray Fluorescence',            label_tr: 'XRF Analizi',           nugget: false },
  { value: 'RADIOGRAPHIC',  label_en: 'Radiographic',                  label_tr: 'Radyografik',           nugget: false },
  { value: 'OTHER',         label_en: 'Other Qualified Method',        label_tr: 'Diğer Nitelikli Yöntem', nugget: false },
]

const VERDICT_OPTIONS = [
  { value: 'UNREVIEWED',   label_en: 'Unreviewed',   label_tr: 'İncelenmedi',  color: '#6b7280' },
  { value: 'ACCEPTABLE',   label_en: 'Acceptable',   label_tr: 'Kabul edilebilir', color: '#22c55e' },
  { value: 'REJECTABLE',   label_en: 'Rejectable',   label_tr: 'Reddedilebilir', color: '#ef4444' },
  { value: 'INCONCLUSIVE', label_en: 'Inconclusive', label_tr: 'Belirsiz',     color: '#f59e0b' },
]

const QUALITY_OPTIONS = [
  { value: 'UNVERIFIED',   label_en: 'Unverified',  label_tr: 'Doğrulanmamış', color: '#6b7280' },
  { value: 'VERIFIED',     label_en: 'Verified (report ref required)', label_tr: 'Doğrulandı (rapor ref gerekli)', color: '#22c55e' },
  { value: 'INSUFFICIENT', label_en: 'Insufficient', label_tr: 'Yetersiz',    color: '#ef4444' },
]

interface EvidenceRecord {
  id: number
  image_path: string
  weld_id: string | null
  test_method: string
  test_date: string | null
  test_operator: string | null
  test_report_ref: string | null
  test_facility: string | null
  nugget_diameter_mm: number | null
  nugget_height_mm: number | null
  confirmed_defect_codes: string
  verdict: string
  acceptance_standard: string | null
  evidence_quality: string
  notes: string
  created_by: string
  created_at: string
}

interface EvidenceSummary {
  total: number
  by_method: Record<string, number>
  by_verdict: Record<string, number>
  by_quality: Record<string, number>
  images_with_evidence: number
  total_dataset_images: number
  e4_gap_pct: number
}

function verdictColor(v: string): string {
  return VERDICT_OPTIONS.find(o => o.value === v)?.color ?? '#6b7280'
}

function qualityColor(q: string): string {
  return QUALITY_OPTIONS.find(o => o.value === q)?.color ?? '#6b7280'
}

const emptyForm = {
  image_path: '',
  weld_id: '',
  test_method: '',
  test_date: '',
  test_operator: '',
  test_report_ref: '',
  test_facility: '',
  nugget_diameter_mm: '',
  nugget_height_mm: '',
  confirmed_defect_codes: '',
  verdict: 'UNREVIEWED',
  acceptance_standard: '',
  evidence_quality: 'UNVERIFIED',
  notes: '',
}

export function E4EvidencePage() {
  const { lang } = useAppLanguage()
  const [records, setRecords] = useState<EvidenceRecord[]>([])
  const [summary, setSummary] = useState<EvidenceSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ ...emptyForm })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [filterMethod, setFilterMethod] = useState('')

  const authHeaders = getAuthHeaders()

  const fetchRecords = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '200', offset: '0' })
      if (filterMethod) params.set('test_method', filterMethod)
      const res = await fetch(`${API}/e4-evidence?${params}`, { headers: authHeaders })
      if (res.ok) {
        const data = await res.json()
        setRecords(data.items ?? [])
      }
    } finally { setLoading(false) }
  }, [filterMethod])

  const fetchSummary = useCallback(async () => {
    const res = await fetch(`${API}/e4-evidence/summary`, { headers: authHeaders })
    if (res.ok) setSummary(await res.json())
  }, [])

  useEffect(() => {
    fetchRecords()
    fetchSummary()
  }, [fetchRecords, fetchSummary])

  const selectedMethod = TEST_METHODS.find(m => m.value === form.test_method)
  const nuggetAllowed = selectedMethod?.nugget ?? false

  function setField(k: keyof typeof emptyForm, v: string) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  async function handleSubmit() {
    setError(''); setSuccess('')
    if (!form.image_path.trim()) { setError(lang === 'tr' ? 'Görüntü yolu gerekli.' : 'Image path is required.'); return }
    if (!form.test_method) { setError(lang === 'tr' ? 'Test yöntemi seçiniz.' : 'Select a test method.'); return }
    if (form.evidence_quality === 'VERIFIED' && !form.test_report_ref.trim()) {
      setError(lang === 'tr'
        ? 'DOĞRULANMIŞ kalite için rapor referansı zorunludur.'
        : 'Report reference is required for VERIFIED evidence quality.')
      return
    }
    if ((form.nugget_diameter_mm || form.nugget_height_mm) && !nuggetAllowed) {
      setError(lang === 'tr'
        ? 'Çekirdek ölçümü yalnızca CROSS_SECTION veya UT_SCAN için geçerlidir.'
        : 'Nugget measurements are only valid for CROSS_SECTION or UT_SCAN.')
      return
    }
    setSubmitting(true)
    try {
      const body: Record<string, unknown> = {
        image_path: form.image_path.trim(),
        test_method: form.test_method,
        verdict: form.verdict,
        evidence_quality: form.evidence_quality,
        notes: form.notes.trim(),
        confirmed_defect_codes: form.confirmed_defect_codes.trim(),
      }
      if (form.weld_id.trim()) body.weld_id = form.weld_id.trim()
      if (form.test_date.trim()) body.test_date = form.test_date.trim()
      if (form.test_operator.trim()) body.test_operator = form.test_operator.trim()
      if (form.test_report_ref.trim()) body.test_report_ref = form.test_report_ref.trim()
      if (form.test_facility.trim()) body.test_facility = form.test_facility.trim()
      if (form.acceptance_standard.trim()) body.acceptance_standard = form.acceptance_standard.trim()
      if (nuggetAllowed && form.nugget_diameter_mm.trim()) body.nugget_diameter_mm = parseFloat(form.nugget_diameter_mm)
      if (nuggetAllowed && form.nugget_height_mm.trim()) body.nugget_height_mm = parseFloat(form.nugget_height_mm)

      const res = await fetch(`${API}/e4-evidence`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const e = await res.json()
        throw new Error(e.detail || `HTTP ${res.status}`)
      }
      setSuccess(lang === 'tr' ? 'Kanıt kaydedildi.' : 'Evidence recorded.')
      setForm({ ...emptyForm })
      await Promise.all([fetchRecords(), fetchSummary()])
    } catch (e: unknown) {
      setError(String(e instanceof Error ? e.message : e))
    } finally { setSubmitting(false) }
  }

  const coveragePct = summary
    ? Math.round((summary.images_with_evidence / Math.max(summary.total_dataset_images, 1)) * 100)
    : 0

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif', color: '#f9fafb',
                  maxWidth: 1400, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, flex: 1 }}>
            {lang === 'tr' ? 'E4 Fiziksel Test Kanıtı' : 'E4 Physical Test Evidence'}
          </h1>
          <ModuleReadButton moduleId="e4_evidence" />
        </div>
        <p style={{ margin: '4px 0 0', color: '#9ca3af', fontSize: 13 }}>
          {lang === 'tr'
            ? 'Nitelikli yıkıcı ve NDT test sonuçlarını kaydedin. Yüzey gözlemi kabul edilmez.'
            : 'Record qualified destructive and NDT test results. Surface observations are not accepted here.'}
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px', background: '#1f2937', borderRadius: 8, padding: '10px 14px',
                        border: '1px solid #374151' }}>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
              {lang === 'tr' ? 'Fiziksel Test Kapsamı' : 'Physical Test Coverage'}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: coveragePct >= 20 ? '#22c55e' : '#f59e0b' }}>
              {coveragePct}%
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af' }}>
              {summary.images_with_evidence}/{summary.total_dataset_images} {lang === 'tr' ? 'görüntü' : 'images'}
            </div>
          </div>

          <div style={{ flex: '1 1 200px', background: '#7f1d1d22', borderRadius: 8, padding: '10px 14px',
                        border: '1px solid #dc2626' }}>
            <div style={{ fontSize: 11, color: '#fca5a5', fontWeight: 700, marginBottom: 4 }}>
              ✗ E4 Gate — {lang === 'tr' ? 'Fiziksel Kanıt' : 'Physical Evidence'}
            </div>
            <div style={{ fontSize: 11, color: '#6b7280' }}>
              {lang === 'tr'
                ? `${summary.total_dataset_images - summary.images_with_evidence} görüntü fiziksel test bekliyor`
                : `${summary.total_dataset_images - summary.images_with_evidence} images still need physical testing`}
            </div>
          </div>

          <div style={{ flex: '1 1 200px', background: '#1f2937', borderRadius: 8, padding: '10px 14px',
                        border: '1px solid #374151' }}>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
              {lang === 'tr' ? 'Kayıtlar' : 'Records'}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#d1d5db' }}>{summary.total}</div>
            <div style={{ fontSize: 10, color: '#6b7280' }}>
              {Object.entries(summary.by_method).map(([m, n]) =>
                `${m.replace('_', ' ')}: ${n}`).join(' · ')}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 20 }}>

        {/* Evidence list */}
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={filterMethod} onChange={e => setFilterMethod(e.target.value)}
              style={{ background: '#1f2937', color: '#f9fafb', border: '1px solid #374151',
                       borderRadius: 6, padding: '5px 10px', fontSize: 11, cursor: 'pointer' }}>
              <option value="">{lang === 'tr' ? 'Tüm yöntemler' : 'All methods'}</option>
              {TEST_METHODS.map(m => (
                <option key={m.value} value={m.value}>
                  {lang === 'tr' ? m.label_tr : m.label_en}
                </option>
              ))}
            </select>
            <span style={{ fontSize: 11, color: '#6b7280' }}>
              {records.length} {lang === 'tr' ? 'kayıt' : 'records'}
            </span>
          </div>

          {loading ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>{lang === 'tr' ? 'Yükleniyor…' : 'Loading…'}</div>
          ) : records.length === 0 ? (
            <div style={{ background: '#1f2937', borderRadius: 8, padding: 32, textAlign: 'center',
                          border: '1px solid #374151', color: '#6b7280', fontSize: 13 }}>
              {lang === 'tr'
                ? 'Henüz fiziksel test kanıtı kaydedilmemiş.'
                : 'No physical test evidence recorded yet.'}
              <div style={{ marginTop: 8, fontSize: 12, color: '#4b5563' }}>
                {lang === 'tr'
                  ? 'Sağdaki formu kullanarak ilk kaydı ekleyin.'
                  : 'Use the form on the right to add the first record.'}
              </div>
            </div>
          ) : (
            <div style={{ maxHeight: 640, overflowY: 'auto' }}>
              {records.map(r => (
                <div key={r.id} onClick={() => setSelectedId(selectedId === r.id ? null : r.id)}
                  style={{ cursor: 'pointer', padding: '10px 14px', marginBottom: 8, borderRadius: 8,
                           background: selectedId === r.id ? '#1e3a5f' : '#1f2937',
                           border: `1px solid ${selectedId === r.id ? '#3b82f6' : '#374151'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#d1d5db' }}>
                      {r.test_method.replace('_', ' ')}
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <span style={{ fontSize: 10, color: verdictColor(r.verdict),
                                     background: verdictColor(r.verdict) + '22', padding: '1px 6px', borderRadius: 3 }}>
                        {r.verdict}
                      </span>
                      <span style={{ fontSize: 10, color: qualityColor(r.evidence_quality),
                                     background: qualityColor(r.evidence_quality) + '22', padding: '1px 6px', borderRadius: 3 }}>
                        {r.evidence_quality}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: 10, color: '#9ca3af', wordBreak: 'break-all' }}>
                    {r.image_path.split(/[\\/]/).pop()}
                  </div>
                  {selectedId === r.id && (
                    <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 10 }}>
                      {r.weld_id && <><span style={{ color: '#6b7280' }}>Weld ID</span><span style={{ color: '#d1d5db' }}>{r.weld_id}</span></>}
                      {r.test_date && <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Tarih' : 'Date'}</span><span style={{ color: '#d1d5db' }}>{r.test_date}</span></>}
                      {r.test_operator && <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Teknisyen' : 'Operator'}</span><span style={{ color: '#d1d5db' }}>{r.test_operator}</span></>}
                      {r.test_report_ref && <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Rapor Ref' : 'Report Ref'}</span><span style={{ color: '#d1d5db' }}>{r.test_report_ref}</span></>}
                      {r.test_facility && <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Laboratuvar' : 'Facility'}</span><span style={{ color: '#d1d5db' }}>{r.test_facility}</span></>}
                      {r.nugget_diameter_mm != null && (
                        <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Çekirdek Çapı' : 'Nugget Ø'}</span>
                        <span style={{ color: '#fbbf24' }}>{r.nugget_diameter_mm} mm</span></>
                      )}
                      {r.nugget_height_mm != null && (
                        <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Çekirdek Y.' : 'Nugget H.'}</span>
                        <span style={{ color: '#fbbf24' }}>{r.nugget_height_mm} mm</span></>
                      )}
                      {r.confirmed_defect_codes && (
                        <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Hata Kodları' : 'Defect Codes'}</span>
                        <span style={{ color: '#d1d5db' }}>{r.confirmed_defect_codes}</span></>
                      )}
                      {r.acceptance_standard && (
                        <><span style={{ color: '#6b7280' }}>{lang === 'tr' ? 'Standart' : 'Standard'}</span>
                        <span style={{ color: '#d1d5db' }}>{r.acceptance_standard}</span></>
                      )}
                      {r.notes && (
                        <div style={{ gridColumn: '1/-1', color: '#9ca3af', marginTop: 4, fontStyle: 'italic' }}>
                          {r.notes}
                        </div>
                      )}
                      <div style={{ gridColumn: '1/-1', color: '#4b5563', marginTop: 6 }}>
                        {lang === 'tr' ? 'Kaydeden:' : 'By:'} {r.created_by} · {r.created_at.slice(0, 10)}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Entry form */}
        <div style={{ background: '#1f2937', borderRadius: 10, padding: 20, border: '1px solid #374151',
                      alignSelf: 'start', position: 'sticky', top: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#d1d5db', marginBottom: 16 }}>
            {lang === 'tr' ? 'Yeni Kanıt Ekle' : 'Add New Evidence'}
          </div>

          {error && (
            <div style={{ background: '#7f1d1d', border: '1px solid #dc2626', borderRadius: 6,
                          padding: '8px 12px', marginBottom: 12, fontSize: 12, color: '#fca5a5' }}>
              {error}
            </div>
          )}
          {success && (
            <div style={{ background: '#14532d', border: '1px solid #16a34a', borderRadius: 6,
                          padding: '8px 12px', marginBottom: 12, fontSize: 12, color: '#86efac' }}>
              {success}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <FormField label={lang === 'tr' ? 'Görüntü Yolu *' : 'Image Path *'}>
              <input value={form.image_path} onChange={e => setField('image_path', e.target.value)}
                placeholder={lang === 'tr' ? 'D:\\...\\image.png' : 'D:\\...\\image.png'}
                style={inputStyle} />
              <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                {lang === 'tr'
                  ? 'Orijinal görüntü yolu (mutlak). Dosya değiştirilmez.'
                  : 'Absolute path to original image. File is never modified.'}
              </div>
            </FormField>

            <FormField label={lang === 'tr' ? 'Kaynak Yöntemi *' : 'Test Method *'}>
              <select value={form.test_method} onChange={e => setField('test_method', e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}>
                <option value="">{lang === 'tr' ? '— yöntem seçin —' : '— select method —'}</option>
                {TEST_METHODS.map(m => (
                  <option key={m.value} value={m.value}>
                    {lang === 'tr' ? m.label_tr : m.label_en}
                  </option>
                ))}
              </select>
              {form.test_method && (
                <div style={{ fontSize: 10, color: nuggetAllowed ? '#86efac' : '#6b7280', marginTop: 2 }}>
                  {nuggetAllowed
                    ? (lang === 'tr' ? '✓ Çekirdek ölçümüne izin verilir.' : '✓ Nugget measurements allowed.')
                    : (lang === 'tr' ? 'Çekirdek ölçümü bu yöntem için geçersiz.' : 'Nugget measurements not applicable for this method.')}
                </div>
              )}
            </FormField>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <FormField label={lang === 'tr' ? 'Kaynak Tarihi' : 'Test Date'}>
                <input type="date" value={form.test_date} onChange={e => setField('test_date', e.target.value)}
                  style={inputStyle} />
              </FormField>
              <FormField label={lang === 'tr' ? 'Teknik Uzman' : 'Test Operator'}>
                <input value={form.test_operator} onChange={e => setField('test_operator', e.target.value)}
                  placeholder={lang === 'tr' ? 'ad veya rozet' : 'name or badge'}
                  style={inputStyle} />
              </FormField>
            </div>

            <FormField label={lang === 'tr' ? 'Rapor Referansı' : 'Report Reference'}>
              <input value={form.test_report_ref} onChange={e => setField('test_report_ref', e.target.value)}
                placeholder={lang === 'tr' ? 'dok. no / rapor no' : 'doc no / report no'}
                style={inputStyle} />
            </FormField>

            <FormField label={lang === 'tr' ? 'Laboratuvar / Tesis' : 'Test Facility'}>
              <input value={form.test_facility} onChange={e => setField('test_facility', e.target.value)}
                placeholder={lang === 'tr' ? 'lab adı' : 'facility name'}
                style={inputStyle} />
            </FormField>

            {nuggetAllowed && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <FormField label={lang === 'tr' ? 'Çekirdek Çapı (mm)' : 'Nugget Diameter (mm)'}>
                  <input type="number" step="0.01" min="0" value={form.nugget_diameter_mm}
                    onChange={e => setField('nugget_diameter_mm', e.target.value)}
                    placeholder="mm" style={inputStyle} />
                </FormField>
                <FormField label={lang === 'tr' ? 'Çekirdek Yüksekliği (mm)' : 'Nugget Height (mm)'}>
                  <input type="number" step="0.01" min="0" value={form.nugget_height_mm}
                    onChange={e => setField('nugget_height_mm', e.target.value)}
                    placeholder="mm" style={inputStyle} />
                </FormField>
              </div>
            )}

            <FormField label={lang === 'tr' ? 'Onaylanan Hata Kodları' : 'Confirmed Defect Codes'}>
              <input value={form.confirmed_defect_codes}
                onChange={e => setField('confirmed_defect_codes', e.target.value)}
                placeholder="ok, capak, kopuk, …"
                style={inputStyle} />
              <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>
                {lang === 'tr' ? 'Virgülle ayrılmış, fiziksel testlerle onaylanan.' : 'Comma-separated, confirmed by this physical test.'}
              </div>
            </FormField>

            <FormField label={lang === 'tr' ? 'Karar' : 'Verdict'}>
              <select value={form.verdict} onChange={e => setField('verdict', e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}>
                {VERDICT_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>
                    {lang === 'tr' ? o.label_tr : o.label_en}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label={lang === 'tr' ? 'Kabul Standardı' : 'Acceptance Standard'}>
              <input value={form.acceptance_standard}
                onChange={e => setField('acceptance_standard', e.target.value)}
                placeholder="ISO 15614-12, AWS D8.1, OEM-123, …"
                style={inputStyle} />
            </FormField>

            <FormField label={lang === 'tr' ? 'Kanıt Kalitesi' : 'Evidence Quality'}>
              <select value={form.evidence_quality} onChange={e => setField('evidence_quality', e.target.value)}
                style={{ ...inputStyle, cursor: 'pointer' }}>
                {QUALITY_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>
                    {lang === 'tr' ? o.label_tr : o.label_en}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label={lang === 'tr' ? 'Kaynak Kimliği' : 'Weld ID'}>
              <input value={form.weld_id} onChange={e => setField('weld_id', e.target.value)}
                placeholder={lang === 'tr' ? 'üretim kaynak ID (opsiyonel)' : 'production weld ID (optional)'}
                style={inputStyle} />
            </FormField>

            <FormField label={lang === 'tr' ? 'Notlar' : 'Notes'}>
              <textarea value={form.notes} onChange={e => setField('notes', e.target.value)}
                rows={3}
                placeholder={lang === 'tr' ? 'Ek gözlemler…' : 'Additional observations…'}
                style={{ ...inputStyle, resize: 'vertical' }} />
            </FormField>

            <button onClick={handleSubmit} disabled={submitting}
              style={{ padding: '10px 20px', borderRadius: 6, fontSize: 13, fontWeight: 700,
                       background: submitting ? '#374151' : '#3b82f6', color: '#f9fafb',
                       border: 'none', cursor: submitting ? 'not-allowed' : 'pointer', marginTop: 4 }}>
              {submitting
                ? (lang === 'tr' ? 'Kaydediliyor…' : 'Saving…')
                : (lang === 'tr' ? 'Kanıtı Kaydet' : 'Save Evidence')}
            </button>

            <div style={{ fontSize: 10, color: '#6b7280', paddingTop: 4,
                          borderTop: '1px solid #374151', marginTop: 4 }}>
              {lang === 'tr'
                ? 'Bu kayıt eğitim geçidini otomatik olarak değiştirmez. Kalite Mühendisi onayı gereklidir.'
                : 'This record does not automatically change the training gate. Quality Engineer sign-off required.'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 3 }}>{label}</div>
      {children}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  background: '#111827',
  color: '#f9fafb',
  border: '1px solid #374151',
  borderRadius: 5,
  padding: '6px 8px',
  fontSize: 11,
}
