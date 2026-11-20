import { useState, useRef, useCallback, useEffect } from 'react'
import apiClient from '../api/client'
import { ModuleReadButton } from '../components/ModuleReadPanel'

// ── Types ────────────────────────────────────────────────────────────────────

type InspectionStatus = 'OK' | 'NOK' | 'REVIEW' | 'UNKNOWN' | 'NOT_EVALUATED'
type MeasurementSource = 'MEASURED' | 'PREDICTED' | 'NOT_AVAILABLE'
type ImageType = 'SURFACE' | 'CROSS_SECTION' | 'UNKNOWN'
type VisualFindingStatus = 'DETECTED' | 'NOT_DETECTED' | 'NOT_EVALUATED'
type ReviewVerdict = 'AGREE' | 'DISAGREE' | 'FURTHER_REVIEW'
type VisualVerdict = 'OK' | 'NOK' | 'REVIEW' | 'NOT_EVALUATED'
type Lang = 'tr' | 'en'

interface ImageMetadata {
  width_px: number; height_px: number; channels: number
  format_detected: string; file_size_bytes: number
}
interface ElectrodeIndentation {
  diameter_mm: number | null; area_mm2: number | null
  source: MeasurementSource; confidence: number; contour_quality: string; notes: string[]
}
interface DefectRegion {
  label: string; bbox_pixels: [number, number, number, number]
  area_mm2: number | null; source: MeasurementSource; confidence: number
}
interface NuggetMeasurement {
  diameter_mm: number | null; area_mm2: number | null; source: MeasurementSource; notes: string[]
}
interface CalibrationConfig { pixels_per_mm: number; reference_method: string }
interface VisualFinding {
  code: string; status: VisualFindingStatus; name_en: string; name_tr: string
  evidence: string; source: string; limitations: string; confidence: number | null
  bbox_pixels: [number, number, number, number] | null
  next_action_en: string; next_action_tr: string; internal_weld_integrity: string
}
interface InspectionResult {
  inspection_id: string; timestamp: string; image_type: ImageType; status: InspectionStatus
  image_metadata: ImageMetadata; electrode_indentation: ElectrodeIndentation | null
  defects: DefectRegion[]; nugget: NuggetMeasurement | null; visual_findings: VisualFinding[]
  preprocessing_notes: string[]; review_notes: string[]; calibration: CalibrationConfig | null
}
interface InspectionReview {
  id: number; inspection_id: string; reviewer_username: string; reviewer_role: string
  verdict: ReviewVerdict; comment: string; created_at: string; is_training_label: boolean
}

// ── Localisation ─────────────────────────────────────────────────────────────

const T = {
  tr: {
    pageTitle:        'Statik Muayene',
    pageDesc:         'Kaynak yüzey görüntüsü veya kesit yükleyin. Tüm ölçümler kaynağını gösterir. Kalite durumu için kabul kriterleri gereklidir.',
    uploadHint:       'Sürükle & bırak veya tıklayın (JPEG, PNG, TIFF, BMP, WebP · maks 50 MB)',
    imgType:          'Görüntü Tipi', imgTypeUnknown: 'Bilinmiyor',
    imgTypeSurface:   'Yüzey (elektrot görünümü)', imgTypeCross: 'Kesit',
    calibration:      'Kalibrasyon (px/mm)',
    roi:              'İlgi Alanı (isteğe bağlı)',
    criteria:         'Kabul Kriterleri (isteğe bağlı — OK/NOK için gerekli)',
    criteriaDesc:     'Eşikler onaylı tahrip deney veya standarttan gelmelidir. Kriterler olmadan durum DEĞERLENDİRİLMEDİ olur.',
    minNugget:        'Min Nugget Çapı (mm)', maxNugget: 'Maks Nugget Çapı (mm)',
    maxDefects:       'Maks Hata Bölgesi', criteriaVer: 'Kriter Versiyonu',
    analyze:          'Muayeneyi Çalıştır', analyzing: 'Analiz ediliyor…',
    statusLabel:      'Durum', imgTypeLabel: 'Görüntü Tipi', dimensions: 'Boyutlar',
    format:           'Format', inspectionId: 'Muayene ID',
    addCriteriaHint:  'Yorum almak için kabul kriterleri ekleyin',
    electrodeTitle:   'Elektrot İzi', diameter: 'Çap', area: 'Alan', confidence: 'Güven',
    contourQ:         'Kontur Kalitesi', nuggetTitle: 'Nugget Ölçümü',
    vfTitle:          'Görsel Hata Modu Analizi',
    vfDisclaimer:     '(yalnızca yüzey görüntüsü — nugget kabul durumunu doğrulamaz)',
    defectsTitle:     'Hata Bölgeleri', noDefects: 'Anomalous bölge tespit edilmedi.',
    notesTitle:       'Notlar',
    addReviewBtn:     'Mühendis Yorumu Ekle',
    reviewPanelTitle: 'Mühendis Değerlendirmesi',
    reviewPanelSub:   'Görsel bulgular yapay zeka tarafından üretilmiştir. Yorum eğitim etiketi değildir.',
    verdictLabel:     'Değerlendirme', verdictAgree: 'Onaylıyorum',
    verdictDisagree:  'Katılmıyorum', verdictFurther: 'İleri İnceleme',
    commentLabel:     'Yorum (min. 10 karakter)', commentPlaceholder: 'Mühendislik değerlendirmenizi yazın…',
    submitBtn:        'Yorum Kaydet', submitting: 'Kaydediliyor…',
    commentTooShort:  'Yorum en az 10 karakter olmalıdır.',
    submitError:      'Yorum kaydedilemedi: ',
    submitSuccess:    'Yorum kaydedildi.',
    prevReviews:      'Önceki Yorumlar',
    noPrevReviews:    'Bu muayene için henüz yorum yok.',
    close:            'Kapat',
    visualVerdict:    'Görsel Kalite Kararı',
    primaryDefect:    'Birincil Hata Modu',
    noDefectMode:     'Tespit edilmedi',
    integrityNote:    'İç kaynak bütünlüğü yalnızca tahrip veya NDT ile onaylanabilir.',
    reviewedBy:       'Değerlendiren',
    reviewedAt:       'Tarih',
  },
  en: {
    pageTitle:        'Static Inspection',
    pageDesc:         'Upload a weld surface image or cross-section. All measurements show their source. Quality status requires explicit acceptance criteria.',
    uploadHint:       'Drag and drop or click to select (JPEG, PNG, TIFF, BMP, WebP · max 50 MB)',
    imgType:          'Image Type', imgTypeUnknown: 'Unknown',
    imgTypeSurface:   'Surface (electrode view)', imgTypeCross: 'Cross-section',
    calibration:      'Calibration (px/mm)',
    roi:              'ROI (optional)',
    criteria:         'Acceptance Criteria (optional — required for OK/NOK verdict)',
    criteriaDesc:     'Thresholds must come from validated destructive testing or accepted standards. Without criteria, status is NOT EVALUATED.',
    minNugget:        'Min Nugget Diameter (mm)', maxNugget: 'Max Nugget Diameter (mm)',
    maxDefects:       'Max Defect Regions', criteriaVer: 'Criteria Version',
    analyze:          'Run Inspection', analyzing: 'Analyzing…',
    statusLabel:      'Status', imgTypeLabel: 'Image Type', dimensions: 'Dimensions',
    format:           'Format', inspectionId: 'Inspection ID',
    addCriteriaHint:  'Add acceptance criteria to get OK/NOK/REVIEW verdict',
    electrodeTitle:   'Electrode Indentation', diameter: 'Diameter', area: 'Area',
    confidence:       'Confidence', contourQ: 'Contour Quality', nuggetTitle: 'Nugget Measurement',
    vfTitle:          'Visual Defect Mode Analysis',
    vfDisclaimer:     '(surface image only — does not confirm nugget acceptance)',
    defectsTitle:     'Defect Regions', noDefects: 'No anomalous regions detected.',
    notesTitle:       'Notes',
    addReviewBtn:     'Add Engineer Comment',
    reviewPanelTitle: 'Engineer Review',
    reviewPanelSub:   'Visual findings are AI-generated. Comments are not training labels.',
    verdictLabel:     'Verdict', verdictAgree: 'Agree',
    verdictDisagree:  'Disagree', verdictFurther: 'Further Review',
    commentLabel:     'Comment (min. 10 characters)', commentPlaceholder: 'Write your engineering assessment…',
    submitBtn:        'Save Comment', submitting: 'Saving…',
    commentTooShort:  'Comment must be at least 10 characters.',
    submitError:      'Failed to save comment: ',
    submitSuccess:    'Comment saved.',
    prevReviews:      'Previous Reviews',
    noPrevReviews:    'No reviews yet for this inspection.',
    close:            'Close',
    visualVerdict:    'Visual Quality Verdict',
    primaryDefect:    'Primary Defect Mode',
    noDefectMode:     'None detected',
    integrityNote:    'Internal weld integrity can only be confirmed by destructive testing or NDT.',
    reviewedBy:       'Reviewed by',
    reviewedAt:       'Date',
  },
} as const

// ── Visual verdict derivation ─────────────────────────────────────────────────

const WELD_DEFECT_CODES = new Set([
  'MISSING_WELD_INDICATION', 'SURFACE_SPATTER', 'SUSPECTED_SURFACE_CRACK',
  'SURFACE_DISCOLORATION', 'ELECTRODE_MISALIGNMENT', 'ELLIPTICAL_INDENTATION',
  'DOUBLE_SPOT_INDICATION', 'MULTIPLE_WELD_POINTS',
])
const IMG_QUALITY_CODES = new Set(['IMAGE_BLUR', 'INSUFFICIENT_LIGHTING', 'IMAGE_NOISE'])

function deriveVisualVerdict(findings: VisualFinding[]): VisualVerdict {
  if (!findings.length) return 'NOT_EVALUATED'
  const det = (code: string) => findings.some(f => f.code === code && f.status === 'DETECTED')
  const detectedWeld = findings.some(f => WELD_DEFECT_CODES.has(f.code) && f.status === 'DETECTED')
  const detectedImgQ = findings.some(f => IMG_QUALITY_CODES.has(f.code) && f.status === 'DETECTED')
  if (detectedWeld) return 'NOK'
  if (detectedImgQ) return 'REVIEW'
  if (det('NORMAL_SURFACE')) return 'OK'
  return 'NOT_EVALUATED'
}

function primaryDefectCode(findings: VisualFinding[]): VisualFinding | null {
  const weldDefects = findings.filter(f => WELD_DEFECT_CODES.has(f.code) && f.status === 'DETECTED')
  if (weldDefects.length) return weldDefects[0]
  const imgQ = findings.filter(f => IMG_QUALITY_CODES.has(f.code) && f.status === 'DETECTED')
  if (imgQ.length) return imgQ[0]
  return null
}

// ── Style helpers ─────────────────────────────────────────────────────────────

const VERDICT_STYLE: Record<VisualVerdict, { bg: string; label: string }> = {
  OK:            { bg: '#16a34a', label: 'OK' },
  NOK:           { bg: '#dc2626', label: 'NOK' },
  REVIEW:        { bg: '#d97706', label: 'REVIEW' },
  NOT_EVALUATED: { bg: '#374151', label: 'NOT EVALUATED' },
}

const STATUS_STYLE: Record<InspectionStatus, { bg: string; label: string }> = {
  OK:            { bg: '#16a34a', label: 'OK' },
  NOK:           { bg: '#dc2626', label: 'NOK' },
  REVIEW:        { bg: '#d97706', label: 'REVIEW' },
  UNKNOWN:       { bg: '#6b7280', label: 'UNKNOWN' },
  NOT_EVALUATED: { bg: '#374151', label: 'NOT EVALUATED' },
}

const REVIEW_VERDICT_STYLE: Record<ReviewVerdict, { bg: string; label_tr: string; label_en: string }> = {
  AGREE:          { bg: '#16a34a', label_tr: 'Onaylıyorum',    label_en: 'Agree' },
  DISAGREE:       { bg: '#dc2626', label_tr: 'Katılmıyorum',   label_en: 'Disagree' },
  FURTHER_REVIEW: { bg: '#d97706', label_tr: 'İleri İnceleme', label_en: 'Further Review' },
}

const VF_STATUS_STYLE: Record<VisualFindingStatus, { bg: string; fg: string; label: string }> = {
  DETECTED:      { bg: '#dc2626', fg: '#fff', label: 'DETECTED' },
  NOT_DETECTED:  { bg: '#16a34a', fg: '#fff', label: 'NOT DETECTED' },
  NOT_EVALUATED: { bg: '#374151', fg: '#d1d5db', label: 'NOT EVALUATED' },
}

function StatusBadge({ status }: { status: InspectionStatus }) {
  const { bg, label } = STATUS_STYLE[status] ?? STATUS_STYLE.UNKNOWN
  return (
    <span style={{ display: 'inline-block', background: bg, color: '#fff',
      padding: '3px 10px', borderRadius: 4, fontWeight: 700, fontSize: 13, letterSpacing: '0.05em' }}>
      {label}
    </span>
  )
}

function SourceTag({ source }: { source: MeasurementSource }) {
  const colors: Record<MeasurementSource, string> = {
    MEASURED: '#1d4ed8', PREDICTED: '#7c3aed', NOT_AVAILABLE: '#6b7280',
  }
  return (
    <span style={{ fontSize: 11, background: colors[source], color: '#fff',
      padding: '1px 6px', borderRadius: 3, marginLeft: 6, fontWeight: 600 }}>
      {source.replace('_', ' ')}
    </span>
  )
}

// ── Visual Findings Card ──────────────────────────────────────────────────────

function VisualFindingsCard({
  findings, lang, onAddReview,
}: { findings: VisualFinding[]; lang: Lang; onAddReview: () => void }) {
  const t = T[lang]
  const vv = deriveVisualVerdict(findings)
  const primary = primaryDefectCode(findings)
  const { bg: vvBg, label: vvLabel } = VERDICT_STYLE[vv]
  const detected = findings.filter(f => f.status === 'DETECTED')
  const others = findings.filter(f => f.status !== 'DETECTED')

  const row = (f: VisualFinding) => {
    const s = VF_STATUS_STYLE[f.status]
    return (
      <div key={f.code} style={{
        background: '#1f2937',
        border: `1px solid ${f.status === 'DETECTED' ? '#dc2626' : '#374151'}`,
        borderRadius: 6, padding: '12px 14px', marginBottom: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 700, background: s.bg, color: s.fg,
            padding: '2px 8px', borderRadius: 3, letterSpacing: '0.04em' }}>{s.label}</span>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{f.name_en}</span>
          <span style={{ color: '#6b7280', fontSize: 12 }}>/ {f.name_tr}</span>
          <span style={{ color: '#4b5563', fontSize: 11, marginLeft: 'auto' }}>{f.code}</span>
        </div>
        <div style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4 }}>
          <span style={{ color: '#9ca3af', fontSize: 11, marginRight: 4 }}>Evidence:</span>
          {f.evidence}
        </div>
        {f.status === 'DETECTED' && (
          <>
            <div style={{ fontSize: 12, color: '#fbbf24', marginBottom: 2 }}>
              <span style={{ fontWeight: 600 }}>⚡ Next action:</span> {f.next_action_en}
            </div>
            <div style={{ fontSize: 12, color: '#fbbf24', marginBottom: 4 }}>
              <span style={{ fontWeight: 600 }}>Sonraki adım:</span> {f.next_action_tr}
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #374151',
              paddingTop: 4, marginTop: 4 }}>
              <span style={{ fontWeight: 600 }}>Internal integrity:</span> {f.internal_weld_integrity}
            </div>
          </>
        )}
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: f.status === 'DETECTED' ? 4 : 0 }}>
          <span style={{ fontWeight: 600 }}>Source:</span> {f.source}
        </div>
        {f.status === 'DETECTED' && (
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
            <span style={{ fontWeight: 600 }}>Limitations:</span> {f.limitations}
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      {/* Verdict strip */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14,
        flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 3,
            textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t.visualVerdict}</div>
          <span style={{ display: 'inline-block', background: vvBg, color: '#fff',
            padding: '4px 14px', borderRadius: 4, fontWeight: 700, fontSize: 15,
            letterSpacing: '0.06em' }}>{vvLabel}</span>
        </div>
        {primary && (
          <div>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 3,
              textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t.primaryDefect}</div>
            <span data-testid="primary-defect-name" style={{ fontSize: 13, fontWeight: 600, color: '#fca5a5' }}>
              {lang === 'tr' ? primary.name_tr : primary.name_en}
            </span>
          </div>
        )}
        {!primary && vv === 'NOT_EVALUATED' && (
          <div style={{ fontSize: 12, color: '#6b7280' }}>{t.noDefectMode}</div>
        )}
        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={onAddReview}
            style={{
              padding: '8px 16px', background: '#1d4ed8', color: '#fff',
              border: 'none', borderRadius: 6, fontWeight: 600, fontSize: 13,
              cursor: 'pointer', letterSpacing: '0.02em',
            }}
            data-testid="add-review-btn"
          >
            + {t.addReviewBtn}
          </button>
        </div>
      </div>

      <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 10,
        fontStyle: 'italic' }}>{t.integrityNote}</div>

      {detected.length === 0 ? (
        <div style={{ fontSize: 14, color: '#6b7280', marginBottom: 8 }}>
          No visual defect modes detected.
        </div>
      ) : (
        <>
          <div style={{ fontSize: 12, color: '#dc2626', fontWeight: 700, marginBottom: 8 }}>
            {detected.length} mode{detected.length > 1 ? 's' : ''} detected
          </div>
          {detected.map(row)}
        </>
      )}
      {others.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontSize: 12, color: '#6b7280', cursor: 'pointer', userSelect: 'none' }}>
            {others.length} not-detected / not-evaluated modes
          </summary>
          <div style={{ marginTop: 8 }}>{others.map(row)}</div>
        </details>
      )}
    </div>
  )
}

// ── Engineer Review Panel ─────────────────────────────────────────────────────

function EngineerReviewPanel({
  inspectionId, snapshot, findings, lang, onClose,
}: {
  inspectionId: string
  snapshot: InspectionResult
  findings: VisualFinding[]
  lang: Lang
  onClose: () => void
}) {
  const t = T[lang]
  const [verdict, setVerdict] = useState<ReviewVerdict>('AGREE')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitMsg, setSubmitMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [prevReviews, setPrevReviews] = useState<InspectionReview[]>([])
  const [panelWidth, setPanelWidth] = useState(440)
  const dragRef = useRef<{ startX: number; startW: number } | null>(null)

  const vv = deriveVisualVerdict(findings)
  const primary = primaryDefectCode(findings)
  const { bg: vvBg, label: vvLabel } = VERDICT_STYLE[vv]

  // Load existing reviews on mount
  useEffect(() => {
    apiClient.get<InspectionReview[]>(`/vision/static/inspect/${inspectionId}/reviews`)
      .then(r => setPrevReviews(r.data))
      .catch(() => {/* ignore load errors */})
  }, [inspectionId])

  // Drag-to-resize from the left edge
  const startDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startW: panelWidth }
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const delta = dragRef.current.startX - ev.clientX
      const newW = Math.max(320, Math.min(820, dragRef.current.startW + delta))
      setPanelWidth(newW)
    }
    const onUp = () => {
      dragRef.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [panelWidth])

  async function handleSubmit() {
    if (comment.trim().length < 10) {
      setSubmitMsg({ ok: false, text: t.commentTooShort })
      return
    }
    setSubmitting(true)
    setSubmitMsg(null)
    try {
      const r = await apiClient.post<InspectionReview>(
        `/vision/static/inspect/${inspectionId}/review`,
        { verdict, comment: comment.trim(), inspection_snapshot: snapshot as unknown as Record<string, unknown> },
      )
      setPrevReviews(prev => [...prev, r.data])
      setComment('')
      setSubmitMsg({ ok: true, text: t.submitSuccess })
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.message || 'unknown error'
      setSubmitMsg({ ok: false, text: t.submitError + msg })
    } finally {
      setSubmitting(false)
    }
  }

  const panelStyle: React.CSSProperties = {
    position: 'fixed', top: 0, right: 0, height: '100%',
    width: panelWidth, background: '#111827', color: '#f9fafb',
    boxShadow: '-4px 0 24px rgba(0,0,0,0.5)',
    display: 'flex', flexDirection: 'column', zIndex: 1000,
    fontFamily: 'system-ui, sans-serif',
  }
  const grabStyle: React.CSSProperties = {
    position: 'absolute', top: 0, left: 0, width: 6, height: '100%',
    cursor: 'col-resize', background: 'transparent',
  }

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 999,
      }} />

      <div style={panelStyle} data-testid="review-panel">
        {/* Drag handle */}
        <div style={grabStyle} onMouseDown={startDrag} />

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '14px 20px',
          borderBottom: '1px solid #1f2937', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{t.reviewPanelTitle}</div>
            <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{t.reviewPanelSub}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none',
            color: '#9ca3af', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}>✕</button>
        </div>

        {/* Body (scrollable) */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

          {/* Visual verdict summary */}
          <div style={{ background: '#1f2937', borderRadius: 8, padding: '12px 14px',
            marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 6,
              textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t.visualVerdict}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ background: vvBg, color: '#fff', padding: '4px 14px',
                borderRadius: 4, fontWeight: 700, fontSize: 15 }}>{vvLabel}</span>
              {primary && (
                <span style={{ fontSize: 13, color: '#fca5a5', fontWeight: 600 }}>
                  {lang === 'tr' ? primary.name_tr : primary.name_en}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: '#6b7280', marginTop: 8, fontStyle: 'italic' }}>
              {t.integrityNote}
            </div>
          </div>

          {/* Verdict selector */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af', marginBottom: 8,
              textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t.verdictLabel}</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(['AGREE', 'DISAGREE', 'FURTHER_REVIEW'] as ReviewVerdict[]).map(v => {
                const vs = REVIEW_VERDICT_STYLE[v]
                const label = lang === 'tr' ? vs.label_tr : vs.label_en
                const selected = verdict === v
                return (
                  <button key={v} onClick={() => setVerdict(v)}
                    data-testid={`verdict-${v.toLowerCase()}`}
                    style={{
                      padding: '8px 16px', border: `2px solid ${selected ? vs.bg : '#374151'}`,
                      background: selected ? vs.bg : 'transparent',
                      color: selected ? '#fff' : '#9ca3af',
                      borderRadius: 6, fontWeight: 600, fontSize: 13, cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}>
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Comment */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#9ca3af',
              textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              {t.commentLabel}
            </label>
            <textarea
              value={comment}
              onChange={e => { setComment(e.target.value); setSubmitMsg(null) }}
              placeholder={t.commentPlaceholder}
              rows={5}
              data-testid="review-comment"
              style={{
                width: '100%', background: '#1f2937', color: '#f9fafb',
                border: '1px solid #374151', borderRadius: 6,
                padding: '8px 10px', fontSize: 13, resize: 'vertical',
                boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            />
            {comment.trim().length > 0 && comment.trim().length < 10 && (
              <div style={{ fontSize: 11, color: '#f87171', marginTop: 4 }}>
                {t.commentTooShort}
              </div>
            )}
          </div>

          {/* Submit message */}
          {submitMsg && (
            <div style={{ fontSize: 13, color: submitMsg.ok ? '#6ee7b7' : '#f87171',
              marginBottom: 12, padding: '8px 12px', background: '#1f2937',
              borderRadius: 6, border: `1px solid ${submitMsg.ok ? '#065f46' : '#7f1d1d'}` }}>
              {submitMsg.text}
            </div>
          )}

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="submit-review"
            style={{
              width: '100%', padding: '10px', background: submitting ? '#374151' : '#1d4ed8',
              color: '#fff', border: 'none', borderRadius: 6, fontWeight: 600,
              fontSize: 14, cursor: submitting ? 'not-allowed' : 'pointer', marginBottom: 24,
            }}>
            {submitting ? t.submitting : t.submitBtn}
          </button>

          {/* Previous reviews */}
          <div style={{ borderTop: '1px solid #1f2937', paddingTop: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#9ca3af',
              textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
              {t.prevReviews}
            </div>
            {prevReviews.length === 0 ? (
              <div style={{ fontSize: 13, color: '#4b5563', fontStyle: 'italic' }}>
                {t.noPrevReviews}
              </div>
            ) : (
              prevReviews.map(rv => {
                const vs = REVIEW_VERDICT_STYLE[rv.verdict]
                const vLabel = lang === 'tr' ? vs.label_tr : vs.label_en
                return (
                  <div key={rv.id} style={{ background: '#1f2937', borderRadius: 6,
                    padding: '10px 12px', marginBottom: 8,
                    border: `1px solid ${vs.bg}44` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, background: vs.bg,
                        color: '#fff', padding: '2px 8px', borderRadius: 3 }}>{vLabel}</span>
                      <span style={{ fontSize: 12, color: '#9ca3af' }}>
                        {t.reviewedBy}: <strong style={{ color: '#d1d5db' }}>{rv.reviewer_username}</strong>
                      </span>
                      <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 'auto' }}>
                        {new Date(rv.created_at).toLocaleString(lang === 'tr' ? 'tr-TR' : 'en-GB')}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.5 }}>
                      {rv.comment}
                    </div>
                    <div style={{ fontSize: 10, color: '#4b5563', marginTop: 4 }}>
                      {t.reviewedAt}: {rv.reviewer_role}
                      {rv.is_training_label ? ' · training label' : ' · not a training label'}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
    </>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function StaticInspectionPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [imageType, setImageType] = useState<ImageType>('UNKNOWN')
  const [pixelsPerMm, setPixelsPerMm] = useState('')
  const [roiX, setRoiX] = useState('')
  const [roiY, setRoiY] = useState('')
  const [roiW, setRoiW] = useState('')
  const [roiH, setRoiH] = useState('')
  const [maxDefects, setMaxDefects] = useState('')
  const [minNuggetDiam, setMinNuggetDiam] = useState('')
  const [maxNuggetDiam, setMaxNuggetDiam] = useState('')
  const [criteriaVersion, setCriteriaVersion] = useState('')
  const [result, setResult] = useState<InspectionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [lang, setLang] = useState<Lang>('tr')
  const [reviewOpen, setReviewOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const t = T[lang]

  const handleFile = useCallback((f: File) => {
    setFile(f)
    setResult(null)
    setError(null)
    setReviewOpen(false)
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target?.result as string)
    reader.readAsDataURL(f)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f && f.type.startsWith('image/')) handleFile(f)
  }, [handleFile])

  async function submit() {
    if (!file) return
    setLoading(true); setError(null); setResult(null); setReviewOpen(false)
    try {
      const fd = new FormData()
      fd.append('image', file)
      fd.append('image_type', imageType)
      if (pixelsPerMm) fd.append('pixels_per_mm', pixelsPerMm)
      if (roiX && roiY && roiW && roiH) {
        fd.append('roi_x', roiX); fd.append('roi_y', roiY)
        fd.append('roi_w', roiW); fd.append('roi_h', roiH)
      }
      if (minNuggetDiam) fd.append('min_nugget_diameter_mm', minNuggetDiam)
      if (maxNuggetDiam) fd.append('max_nugget_diameter_mm', maxNuggetDiam)
      if (maxDefects) fd.append('max_allowed_defects', maxDefects)
      if (criteriaVersion) fd.append('criteria_version', criteriaVersion)
      const r = await apiClient.post<InspectionResult>(
        '/vision/static/inspect', fd,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      setResult(r.data)
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.response?.data?.detail?.message
        || err?.message || 'Request failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const s: React.CSSProperties = { fontFamily: 'system-ui, sans-serif', padding: '0 4px' }
  const card: React.CSSProperties = {
    background: 'var(--card-bg, #f9fafb)', border: '1px solid var(--border, #e5e7eb)',
    borderRadius: 8, padding: '16px 20px', marginBottom: 16,
  }
  const lbl: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--muted, #6b7280)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4,
  }
  const inp: React.CSSProperties = {
    width: '100%', padding: '7px 10px', border: '1px solid var(--border, #d1d5db)',
    borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
  }

  return (
    <div style={s}>
      {/* Title row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{t.pageTitle}</h2>
        <ModuleReadButton moduleId="inspection" />
        <button data-testid="page-lang-toggle" onClick={() => setLang(l => l === 'tr' ? 'en' : 'tr')}
          style={{ marginLeft: 'auto', padding: '4px 10px', border: '1px solid var(--border,#d1d5db)',
            borderRadius: 4, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: 'var(--card-bg,#f9fafb)' }}>
          {lang === 'tr' ? 'EN' : 'TR'}
        </button>
      </div>
      <p style={{ color: 'var(--muted, #6b7280)', fontSize: 14, marginBottom: 20 }}>
        {t.pageDesc}
      </p>

      {/* Upload zone */}
      <div style={{ ...card, border: '2px dashed var(--accent,#3b82f6)', textAlign: 'center',
        cursor: 'pointer', minHeight: 120, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 8 }}
        onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}>
        <input ref={inputRef} type="file" hidden
          accept="image/jpeg,image/png,image/tiff,image/bmp,image/webp"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
        {preview ? (
          <img src={preview} alt="Preview" style={{ maxHeight: 180, maxWidth: '100%', borderRadius: 4 }} />
        ) : (
          <>
            <span style={{ fontSize: 32 }}>🖼</span>
            <span style={{ fontSize: 14, color: 'var(--muted,#6b7280)' }}>{t.uploadHint}</span>
          </>
        )}
        {file && (
          <span style={{ fontSize: 12, color: 'var(--muted,#6b7280)' }}>
            {file.name} · {(file.size / 1024).toFixed(0)} KB
          </span>
        )}
      </div>

      {/* Parameters */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={lbl}>{t.imgType}</label>
          <select style={{ ...inp }} value={imageType} onChange={(e) => setImageType(e.target.value as ImageType)}>
            <option value="UNKNOWN">{t.imgTypeUnknown}</option>
            <option value="SURFACE">{t.imgTypeSurface}</option>
            <option value="CROSS_SECTION">{t.imgTypeCross}</option>
          </select>
        </div>
        <div>
          <label style={lbl}>{t.calibration}</label>
          <input style={inp} type="number" min="0.1" step="0.1" placeholder="e.g. 10.5"
            value={pixelsPerMm} onChange={(e) => setPixelsPerMm(e.target.value)} />
        </div>
      </div>

      {/* ROI */}
      <details style={{ marginBottom: 16 }}>
        <summary style={{ cursor: 'pointer', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{t.roi}</summary>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginTop: 8 }}>
          {[['X', roiX, setRoiX], ['Y', roiY, setRoiY], ['Width', roiW, setRoiW], ['Height', roiH, setRoiH]].map(([ltext, val, set]) => (
            <div key={ltext as string}>
              <label style={lbl}>{ltext as string}</label>
              <input style={inp} type="number" min="0" step="1" placeholder="px"
                value={val as string} onChange={(e) => (set as (v: string) => void)(e.target.value)} />
            </div>
          ))}
        </div>
      </details>

      {/* Acceptance criteria */}
      <details style={{ marginBottom: 20 }}>
        <summary style={{ cursor: 'pointer', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          {t.criteria}
        </summary>
        <p style={{ fontSize: 12, color: 'var(--muted,#6b7280)', margin: '8px 0' }}>{t.criteriaDesc}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 12 }}>
          <div><label style={lbl}>{t.minNugget}</label><input style={inp} type="number" min="0" step="0.1" value={minNuggetDiam} onChange={(e) => setMinNuggetDiam(e.target.value)} /></div>
          <div><label style={lbl}>{t.maxNugget}</label><input style={inp} type="number" min="0" step="0.1" value={maxNuggetDiam} onChange={(e) => setMaxNuggetDiam(e.target.value)} /></div>
          <div><label style={lbl}>{t.maxDefects}</label><input style={inp} type="number" min="0" step="1" value={maxDefects} onChange={(e) => setMaxDefects(e.target.value)} /></div>
          <div><label style={lbl}>{t.criteriaVer}</label><input style={inp} type="text" placeholder="e.g. VW-01-v3.1" value={criteriaVersion} onChange={(e) => setCriteriaVersion(e.target.value)} /></div>
        </div>
      </details>

      <button onClick={submit} disabled={!file || loading} style={{
        padding: '10px 24px', background: file && !loading ? 'var(--accent,#3b82f6)' : '#9ca3af',
        color: '#fff', border: 'none', borderRadius: 6, fontWeight: 600,
        fontSize: 14, cursor: file && !loading ? 'pointer' : 'not-allowed', marginBottom: 24,
      }}>
        {loading ? t.analyzing : t.analyze}
      </button>

      {error && (
        <div style={{ ...card, borderColor: '#fca5a5', background: '#fef2f2', color: '#991b1b', marginBottom: 16 }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div>
          {/* Summary */}
          <div style={{ ...card, display: 'flex', flexWrap: 'wrap', gap: 20, alignItems: 'flex-start' }}>
            <div>
              <div style={lbl}>{t.statusLabel}</div>
              <StatusBadge status={result.status} />
              {result.status === 'NOT_EVALUATED' && (
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{t.addCriteriaHint}</div>
              )}
            </div>
            <div><div style={lbl}>{t.imgTypeLabel}</div><div style={{ fontSize: 14 }}>{result.image_type}</div></div>
            <div>
              <div style={lbl}>{t.dimensions}</div>
              <div style={{ fontSize: 14 }}>{result.image_metadata.width_px} × {result.image_metadata.height_px} px</div>
            </div>
            <div><div style={lbl}>{t.format}</div><div style={{ fontSize: 14 }}>{result.image_metadata.format_detected}</div></div>
            <div>
              <div style={lbl}>{t.inspectionId}</div>
              <div style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 200, wordBreak: 'break-all' }}>
                {result.inspection_id}
              </div>
            </div>
          </div>

          {/* Electrode indentation */}
          {result.electrode_indentation && (
            <div style={card}>
              <div style={{ fontWeight: 700, marginBottom: 10 }}>{t.electrodeTitle}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12 }}>
                <div>
                  <div style={lbl}>{t.diameter}<SourceTag source={result.electrode_indentation.source} /></div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{result.electrode_indentation.diameter_mm != null ? `${result.electrode_indentation.diameter_mm} mm` : '—'}</div>
                </div>
                <div>
                  <div style={lbl}>{t.area}<SourceTag source={result.electrode_indentation.source} /></div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{result.electrode_indentation.area_mm2 != null ? `${result.electrode_indentation.area_mm2} mm²` : '—'}</div>
                </div>
                <div><div style={lbl}>{t.confidence}</div><div style={{ fontSize: 16, fontWeight: 600 }}>{(result.electrode_indentation.confidence * 100).toFixed(0)}%</div></div>
                <div><div style={lbl}>{t.contourQ}</div><div style={{ fontSize: 14 }}>{result.electrode_indentation.contour_quality}</div></div>
              </div>
              {result.electrode_indentation.notes.length > 0 && (
                <ul style={{ margin: '8px 0 0', padding: '0 0 0 16px', fontSize: 12, color: '#6b7280' }}>
                  {result.electrode_indentation.notes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              )}
            </div>
          )}

          {/* Nugget */}
          {result.nugget && (
            <div style={card}>
              <div style={{ fontWeight: 700, marginBottom: 10 }}>{t.nuggetTitle}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12 }}>
                <div>
                  <div style={lbl}>{t.diameter}<SourceTag source={result.nugget.source} /></div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{result.nugget.diameter_mm != null ? `${result.nugget.diameter_mm} mm` : '—'}</div>
                </div>
                <div>
                  <div style={lbl}>{t.area}<SourceTag source={result.nugget.source} /></div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{result.nugget.area_mm2 != null ? `${result.nugget.area_mm2} mm²` : '—'}</div>
                </div>
              </div>
              {result.nugget.notes.length > 0 && (
                <ul style={{ margin: '8px 0 0', padding: '0 0 0 16px', fontSize: 12, color: '#6b7280' }}>
                  {result.nugget.notes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              )}
            </div>
          )}

          {/* Visual defect mode findings */}
          {result.visual_findings && result.visual_findings.length > 0 && (
            <div style={card}>
              <div style={{ fontWeight: 700, marginBottom: 10 }}>
                {t.vfTitle}
                <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 400, marginLeft: 8 }}>
                  {t.vfDisclaimer}
                </span>
              </div>
              <VisualFindingsCard
                findings={result.visual_findings}
                lang={lang}
                onAddReview={() => setReviewOpen(true)}
              />
            </div>
          )}

          {/* Defect regions */}
          <div style={card}>
            <div style={{ fontWeight: 700, marginBottom: 10 }}>
              {t.defectsTitle} ({result.defects.length})
            </div>
            {result.defects.length === 0 ? (
              <div style={{ fontSize: 14, color: '#6b7280' }}>{t.noDefects}</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                    {['#', 'Label', 'Area', 'Source'].map(h => (
                      <th key={h} style={{ textAlign: h === 'Area' ? 'right' : 'left',
                        padding: '4px 8px', color: '#6b7280', fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.defects.map((d, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '4px 8px' }}>{i + 1}</td>
                      <td style={{ padding: '4px 8px' }}>{d.label}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                        {d.area_mm2 != null ? `${d.area_mm2} mm²` : `${d.bbox_pixels[2]}×${d.bbox_pixels[3]} px`}
                      </td>
                      <td style={{ padding: '4px 8px' }}><SourceTag source={d.source} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Notes */}
          {(result.preprocessing_notes.length > 0 || result.review_notes.length > 0) && (
            <div style={card}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>{t.notesTitle}</div>
              {result.preprocessing_notes.map((n, i) => (
                <div key={i} style={{ fontSize: 13, color: '#374151', marginBottom: 4 }}>ℹ {n}</div>
              ))}
              {result.review_notes.map((n, i) => (
                <div key={i} style={{ fontSize: 13, color: '#b45309', marginBottom: 4 }}>⚠ {n}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Engineer review slide-in panel */}
      {reviewOpen && result && (
        <EngineerReviewPanel
          inspectionId={result.inspection_id}
          snapshot={result}
          findings={result.visual_findings}
          lang={lang}
          onClose={() => setReviewOpen(false)}
        />
      )}
    </div>
  )
}
