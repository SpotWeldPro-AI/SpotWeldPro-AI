/**
 * ModuleRead Content Registry
 * Version: 1.0.0
 *
 * Bilingual (TR/EN) structured help content for every application module.
 *
 * Each entry is keyed by page ID (matches App.tsx Page type).
 * Content is based on actual program behavior — no invented acceptance
 * thresholds or unverified standards claims.
 *
 * Section IDs (consistent across all modules):
 *   0 — what_is_this
 *   1 — when_to_use
 *   2 — required_inputs
 *   3 — step_by_step
 *   4 — expected_output
 *   5 — how_to_interpret
 *   6 — common_mistakes
 *   7 — faq
 *   8 — standards_scope
 *   9 — limitations
 *  10 — related_modules
 */

export interface Example {
  id: string
  label: string
  inputs: Record<string, unknown>
  expected_output?: string
}

export interface Section {
  title: string
  content: string
  examples?: Example[]
}

export interface ModuleReadContent {
  module_id: string
  title_tr: string
  title_en: string
  version: string
  sections_tr: Section[]
  sections_en: Section[]
}

const REGISTRY: Record<string, ModuleReadContent> = {

  // ── M01 Dashboard ──────────────────────────────────────────────────────
  dashboard: {
    module_id: 'dashboard',
    title_tr: 'Panel',
    title_en: 'Dashboard',
    version: '1.0.0',
    sections_tr: [
      {
        title: 'Bu modül nedir?',
        content: 'Panel, SpotWeldPro AI sisteminin genel durumunu tek ekranda özetler. Aktif proje sayısı, kaynak noktası sayısı, bekleyen incelemeleri ve model katalog durumunu gösterir.',
      },
      {
        title: 'Ne zaman kullanılır?',
        content: 'Sisteme giriş yaptıktan sonra, günlük durumu hızlıca görmek veya hangi modüllerin dikkat gerektirdiğini anlamak için kullanın.',
      },
      {
        title: 'Gerekli girdiler',
        content: 'Sadece geçerli bir oturum (token) gereklidir. Başka girdi gerekmez.',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Giriş yapın. Sol menüden **Panel** seçeneğine tıklayın. Sayfa otomatik olarak özetleri yükler.',
      },
      {
        title: 'Beklenen çıktı',
        content: 'Proje sayısı, kaynak noktası sayısı, bekleyen anot. incelemesi sayısı ve model sayısını gösteren sayaç kartları.',
      },
      {
        title: 'Sonucu nasıl yorumlanır?',
        content: 'Yüksek bekleyen inceleme sayısı, Çakışma İnceleme modülünde Kalite Mühendisi görevlendirmesi gerektirir.',
      },
      {
        title: 'Yaygın hatalar',
        content: '**401 Yetkisiz**: Oturumunuz sona ermiş olabilir; tekrar giriş yapın.',
      },
      {
        title: 'SSS',
        content: '**S: Veriler ne sıklıkla güncellenir?** C: Her sayfa yenilenişinde.\n\n**S: Farklı kullanıcılar farklı panel görür mü?** C: Evet, her kullanıcı kendi projelerini görür.',
      },
      { title: 'Standartlar', content: 'Bu modül için uygulanabilir endüstriyel standart yoktur.' },
      { title: 'Sınırlamalar', content: 'Panel verileri test veritabanını yansıtır. Üretim verileri için ayrı bir ortam gereklidir.' },
      {
        title: 'İlgili modüller',
        content: '**Projeler** — proje ve kaynak noktası yönetimi\n\n**Çakışma İnceleme** — bekleyen E1 çakışmalarını çözümleme',
      },
    ],
    sections_en: [
      {
        title: 'What is this module?',
        content: 'The Dashboard summarizes the overall state of SpotWeldPro AI on a single screen. It shows the active project count, weld point count, pending reviews, and model catalog status.',
      },
      {
        title: 'When should I use it?',
        content: 'Use it right after login to get a quick system overview or to identify which modules need attention.',
      },
      {
        title: 'Required inputs',
        content: 'Only a valid authentication session token is required. No data inputs needed.',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Log in. Click **Dashboard** in the left navigation. The page loads summaries automatically.',
      },
      {
        title: 'Expected output',
        content: 'Count cards showing: projects, weld points, pending annotation reviews, and model count.',
      },
      {
        title: 'How to interpret the result',
        content: 'A high pending-review count indicates Conflict Review module needs a Quality Engineer assignment.',
      },
      {
        title: 'Common mistakes',
        content: '**401 Unauthorized**: Your session may have expired — log in again.',
      },
      {
        title: 'FAQ',
        content: '**Q: How often does the data refresh?** A: On every page reload.\n\n**Q: Do different users see different dashboards?** A: Yes, each user sees their own projects.',
      },
      { title: 'Standards and scope', content: 'No applicable industrial standard for this module.' },
      { title: 'Limitations', content: 'Dashboard counts reflect the test database. Production data requires a separate environment.' },
      {
        title: 'Related modules',
        content: '**Projects** — project and weld-point management\n\n**Conflict Review** — resolve pending E1 conflicts',
      },
    ],
  },

  // ── M07 Weld Quality Analysis ──────────────────────────────────────────
  analysis: {
    module_id: 'analysis',
    title_tr: 'Kaynak Kalite Analizi',
    title_en: 'Weld Quality Analysis',
    version: '1.0.0',
    sections_tr: [
      {
        title: 'Bu modül nedir?',
        content: 'Kaynak Kalite Analizi, girilen proses parametrelerine göre tahmini bir kalite skoru, risk seviyesi, minimum ve optimum çekirdek çapı ile uyumluluk özeti üretir. Bu bir tahmin modülüdür — endüstriyel doğrulama yerine geçmez.',
      },
      {
        title: 'Ne zaman kullanılır?',
        content: 'Parametreler belirlenirken veya değiştirilirken ön değerlendirme yapmak için kullanın. Nihai kalite kararı için destructive test ve bağımsız doğrulama gereklidir.',
      },
      {
        title: 'Gerekli girdiler',
        content: '**Malzeme ailesi** (mild_steel, galvanized_steel, stainless_steel, hsla)\n\n**Stack sayısı**: 2T veya 3T\n\n**Katmanlar**: Her katman için malzeme + kalınlık (mm) + kaplama durumu\n\n**Akım** (kA), **Kaynak süresi** (çevrim), **Kuvvet** (kN), **Uç çapı** (mm)\n\n**Sıkma/tutma/soğutma** çevrimleri ve soğutma debisi/sıcaklığı',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Soldaki menüden **Kaynak Kalite** seçin.\n\nMalzeme ailesini seçin.\n\nStack sayısını ve her katman için parametreleri girin.\n\nAkım, süre, kuvvet ve uç çapı değerlerini girin.\n\n**Analiz Et** butonuna tıklayın.\n\nSonuçları inceleyin.',
        examples: [
          {
            id: 'weld_analysis_mild_2t',
            label: 'Mild Steel 2T 1.5mm — standart parametre',
            inputs: {
              material_family: 'mild_steel',
              material_subtype: 'DC01',
              stack_count: '2T',
              layers: [
                { material_family: 'mild_steel', material_subtype: 'DC01', thickness_mm: 1.5, coated: false },
                { material_family: 'mild_steel', material_subtype: 'DC01', thickness_mm: 1.5, coated: false },
              ],
              current_ka: 8.0,
              weld_cycles: 12.0,
              force_kn: 3.5,
              tip_diameter_mm: 6.0,
              squeeze_cycles: 10.0,
              hold_cycles: 5.0,
              cooling_flow_lpm: 2.0,
              cooling_temp_c: 20.0,
              dc_current: true,
              adhesive: false,
              shunt_risk: false,
            },
            expected_output: 'score>60, risk=LOW/MEDIUM, nugget_opt_mm≈4.9',
          },
        ],
      },
      {
        title: 'Beklenen çıktı',
        content: '**score**: 0–100 (yüksek = daha iyi kalite)\n\n**risk_level**: LOW / MEDIUM / HIGH / CRITICAL\n\n**nugget_opt_mm**: Tahmin edilen optimum çekirdek çapı\n\n**nugget_min_mm**: AWS D8.9 kriterinden hesaplanan minimum çekirdek çapı (4√t)\n\n**compliance_summary**: Parametrelerin referans profil aralıklarıyla karşılaştırması',
      },
      {
        title: 'Sonucu nasıl yorumlanır?',
        content: '`nugget_opt_mm` değeri `nugget_min_mm` değerinden küçükse risk yüksektir.\n\nSkor 70\'in altında ise parametreler gözden geçirilmelidir.\n\n**Uyarı**: Bu tahmin, fiziksel destructive test ve metalografik kesit analizinin yerini almaz.',
      },
      {
        title: 'Yaygın hatalar',
        content: '**stack_count=4T**: Desteklenmiyor (2T veya 3T).\n\n**current_ka=0**: Geçersiz — pozitif değer girin.\n\n**Katman sayısı stack_count ile uyumsuz**: 2T için 2 katman, 3T için 3 katman gereklidir.',
      },
      {
        title: 'SSS',
        content: '**S: nugget_opt_mm fiziksel ölçüm midir?** C: Hayır, model tahminidir. Gerçek çekirdek çapı kesit analizi ile ölçülür.\n\n**S: AWS D8.9 eşiği otomatik geçer mi?** C: Hayır, `nugget_min_mm = 4√t` bir referans hesaplamadır. Uyumluluk kararı mühendis onayı gerektirir.',
      },
      {
        title: 'Standartlar ve kapsam',
        content: '**AWS D8.9** nugget çapı referans kriteri 4√t formülü için kullanılır (enformasyon amaçlı). **Bu yazılım AWS D8.9 uyumluluk belgesi üretmez.**',
      },
      {
        title: 'Sınırlamalar',
        content: 'Model bağımsız endüstriyel doğrulamadan geçmemiştir. Stainless steel ve HSLA için sınırlı kalibrasyon verisi mevcuttur. Yüzey kaplama etkisi heuristik olarak modellenmektedir.',
      },
      {
        title: 'İlgili modüller',
        content: '**Hata Analizi** — olası hata modları ve olasılıkları\n\n**Kaynak Lobu** — parametrenin güvenli aralığını görselleştir\n\n**Taguchi DOE** — parametrelerin etkisini yapılandırılmış deneylerle araştır',
      },
    ],
    sections_en: [
      {
        title: 'What is this module?',
        content: 'Weld Quality Analysis takes process parameters as input and produces an estimated quality score, risk level, minimum and optimum nugget diameter, and a compliance summary. This is a prediction module — it does not replace industrial validation.',
      },
      {
        title: 'When should I use it?',
        content: 'Use it during parameter development or when evaluating parameter changes. Final quality decisions require destructive testing and independent verification.',
      },
      {
        title: 'Required inputs',
        content: '**Material family**: mild_steel, galvanized_steel, stainless_steel, hsla\n\n**Stack count**: 2T or 3T\n\n**Layers**: each layer needs material + thickness (mm) + coated status\n\n**Current** (kA), **Weld time** (cycles), **Force** (kN), **Tip diameter** (mm)\n\n**Squeeze/hold/cooling** cycles, cooling flow rate and temperature',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Weld Quality Analysis** from the left menu.\n\nChoose a material family.\n\nSet stack count and layer parameters.\n\nEnter current, time, force and tip diameter.\n\nClick **Analyze**.\n\nReview results.',
        examples: [
          {
            id: 'weld_analysis_mild_2t',
            label: 'Mild Steel 2T 1.5mm — standard parameters',
            inputs: {
              material_family: 'mild_steel',
              material_subtype: 'DC01',
              stack_count: '2T',
              layers: [
                { material_family: 'mild_steel', material_subtype: 'DC01', thickness_mm: 1.5, coated: false },
                { material_family: 'mild_steel', material_subtype: 'DC01', thickness_mm: 1.5, coated: false },
              ],
              current_ka: 8.0,
              weld_cycles: 12.0,
              force_kn: 3.5,
              tip_diameter_mm: 6.0,
              squeeze_cycles: 10.0,
              hold_cycles: 5.0,
              cooling_flow_lpm: 2.0,
              cooling_temp_c: 20.0,
              dc_current: true,
              adhesive: false,
              shunt_risk: false,
            },
            expected_output: 'score>60, risk=LOW/MEDIUM, nugget_opt_mm≈4.9',
          },
        ],
      },
      {
        title: 'Expected output',
        content: '**score**: 0–100 (higher = better quality estimate)\n\n**risk_level**: LOW / MEDIUM / HIGH / CRITICAL\n\n**nugget_opt_mm**: Estimated optimum nugget diameter\n\n**nugget_min_mm**: Minimum nugget diameter from AWS D8.9 criterion (4√t)\n\n**compliance_summary**: Parameter comparison against reference profile ranges',
      },
      {
        title: 'How to interpret the result',
        content: 'If `nugget_opt_mm` is below `nugget_min_mm`, risk is high.\n\nA score below 70 warrants parameter review.\n\n**Warning**: This estimate does not replace physical destructive testing or metallographic cross-section analysis.',
      },
      {
        title: 'Common mistakes',
        content: '**stack_count=4T**: Not supported — use 2T or 3T.\n\n**current_ka=0**: Invalid — must be positive.\n\n**Layer count mismatch**: 2T needs 2 layers, 3T needs 3 layers.',
      },
      {
        title: 'FAQ',
        content: '**Q: Is nugget_opt_mm a physical measurement?** A: No, it is a model estimate. Actual nugget diameter must be measured by cross-section analysis.\n\n**Q: Does this automatically pass AWS D8.9?** A: No. `nugget_min_mm = 4√t` is a reference calculation. Compliance decisions require engineer sign-off.',
      },
      {
        title: 'Standards and scope',
        content: '**AWS D8.9** nugget diameter reference criterion (4√t formula) is used for informational purposes only. **This software does not produce AWS D8.9 compliance certificates.**',
      },
      {
        title: 'Limitations',
        content: 'Model has not undergone independent industrial validation. Limited calibration data for stainless steel and HSLA. Surface coating effects are modeled heuristically.',
      },
      {
        title: 'Related modules',
        content: '**Failure Analysis** — probable failure modes and probabilities\n\n**Weld Lobe Lab** — visualize the safe parameter window\n\n**Taguchi DOE** — structured experiments to study parameter effects',
      },
    ],
  },

  // ── M03 Engineering: Weld Lobe ────────────────────────────────────────
  engineering: {
    module_id: 'engineering',
    title_tr: 'Kaynak Mühendisliği',
    title_en: 'Weld Engineering',
    version: '1.0.0',
    sections_tr: [
      {
        title: 'Bu modül nedir?',
        content: 'Kaynak Mühendisliği dört alt sekme içerir: **Kaynak Lobu**, **Elektrot Ömrü**, **Dinamik Direnç** ve **Pulse Stratejisi**. Her sekme belirli bir mühendislik hesabı yapar.',
      },
      {
        title: 'Ne zaman kullanılır?',
        content: 'Parametre penceresi belirlerken (Lob), elektrot bakım planı yaparken (Ömür), direnç örüntüsünü değerlendirirken (Dinamik Direnç) veya darbe stratejisi seçerken kullanın.',
      },
      {
        title: 'Gerekli girdiler',
        content: '**Lob**: Malzeme, kalınlık, kuvvet, minimum çekirdek çapı, akım ve süre aralıkları\n\n**Elektrot Ömrü**: Malzeme, kaplama durumu, uç çapı, soğutma değerleri, akım, yıllık kaynak sayısı\n\n**Dinamik Direnç**: En az 5 µΩ örnek değeri\n\n**Pulse Stratejisi**: Malzeme, kaplama, kalınlık oranı, stack sayısı, yapışkan varlığı, akım, süre',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Sol menüden **Kaynak Lobu** seçin. İstediğiniz alt sekmeye geçin. Parametreleri girin ve **Hesapla** butonuna tıklayın.',
        examples: [
          {
            id: 'weld_lobe_mild_1p5mm',
            label: 'Kaynak Lobu — Mild Steel 1.5mm',
            inputs: {
              material_family: 'mild_steel',
              thickness_mm: 1.5,
              force_kn: 3.5,
              min_nugget_mm: 4.9,
              current_min_ka: 5.0, current_max_ka: 12.0, current_step_ka: 0.5,
              time_min_cycles: 5.0, time_max_cycles: 20.0, time_step_cycles: 1.0,
            },
            expected_output: 'lobe_points ≥ 10, optimum current ~8kA',
          },
          {
            id: 'electrode_life_mild',
            label: 'Elektrot Ömrü — Mild Steel 8kA',
            inputs: {
              material_family: 'mild_steel',
              coated: false,
              tip_diameter_mm: 6.0,
              cooling_flow_lpm: 2.0,
              cooling_temp_c: 20.0,
              current_ka: 8.0,
              annual_spot_count: 50000,
            },
            expected_output: 'estimated_life > 1000 spots',
          },
        ],
      },
      {
        title: 'Beklenen çıktı',
        content: '**Lob**: Güvenli bölge noktaları, optimum nokta, minimum çekirdek çizgisi\n\n**Ömür**: Tahmini ömür (spot), freze aralığı (spot), yıllık takoz sayısı\n\n**Dinamik Direnç**: Kalite değerlendirmesi, tepe/başlangıç/son µΩ, SVG grafik\n\n**Pulse**: Strateji adı, darbe sayısı, karar skoru',
      },
      {
        title: 'Sonucu nasıl yorumlanır?',
        content: 'Küçük bir güvenli lob penceresi, proses kararsızlığına işaret eder. Düşük elektrot ömrü, soğutma veya akım optimizasyonu gerektirir. Dinamik direnç Fault durumu, fiziksel inceleme gerektirir.',
      },
      {
        title: 'Yaygın hatalar',
        content: '**min_length=5 dinamik direnç**: 5\'ten az örnek reddedilir.\n\n**thickness_ratio < 1**: Hata — 1 veya daha büyük olmalı.',
      },
      {
        title: 'SSS',
        content: '**S: Lob hesabı fiziksel deney ile doğrulandı mı?** C: Hayır — analitik model, referans olarak kullanılmalıdır.\n\n**S: Pulse stratejisi üretimde kullanılabilir mi?** C: Yalnızca başlangıç kılavuzu olarak; proses mühendisi onayı gereklidir.',
      },
      {
        title: 'Standartlar',
        content: 'Minimum çekirdek çapı hesabı AWS D8.9 referans formülü 4√t kullanır (enformasyon amaçlı).',
      },
      {
        title: 'Sınırlamalar',
        content: 'Tüm mühendislik modülleri heuristik veya analitik modeldir. Bağımsız endüstriyel doğrulamadan geçmemişlerdir.',
      },
      {
        title: 'İlgili modüller',
        content: '**Kaynak Kalite** — kapsamlı kalite skoru\n\n**Taguchi DOE** — parametre optimizasyonu',
      },
    ],
    sections_en: [
      {
        title: 'What is this module?',
        content: 'The Weld Engineering hub has four sub-tabs: **Weld Lobe Lab**, **Electrode Life Advisor**, **Dynamic Resistance Analyzer**, and **Pulse Strategy Advisor**.',
      },
      {
        title: 'When should I use it?',
        content: 'Use it when defining parameter windows (Lobe), planning electrode maintenance (Electrode Life), evaluating resistance patterns (Dynamic Resistance), or selecting pulse strategies.',
      },
      {
        title: 'Required inputs',
        content: '**Lobe**: Material, thickness, force, min nugget diameter, current and time ranges\n\n**Electrode Life**: Material, coating, tip diameter, cooling values, current, annual spot count\n\n**Dynamic Resistance**: At least 5 µΩ sample values\n\n**Pulse Strategy**: Material, coating, thickness ratio, stack count, adhesive presence, current, time',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Weld Lobe Lab** from the left menu. Switch to the desired sub-tab. Enter parameters and click **Calculate**.',
        examples: [
          {
            id: 'weld_lobe_mild_1p5mm',
            label: 'Weld Lobe — Mild Steel 1.5mm',
            inputs: {
              material_family: 'mild_steel',
              thickness_mm: 1.5,
              force_kn: 3.5,
              min_nugget_mm: 4.9,
              current_min_ka: 5.0, current_max_ka: 12.0, current_step_ka: 0.5,
              time_min_cycles: 5.0, time_max_cycles: 20.0, time_step_cycles: 1.0,
            },
            expected_output: 'lobe_points ≥ 10, optimum current ~8kA',
          },
        ],
      },
      {
        title: 'Expected output',
        content: '**Lobe**: Safe-zone points, optimum point, minimum nugget line\n\n**Life**: Estimated life (spots), dressing interval (spots), annual caps count\n\n**Dynamic Resistance**: Quality assessment, peak/initial/final µΩ, SVG chart\n\n**Pulse**: Strategy name, pulse count, decision score',
      },
      {
        title: 'How to interpret the result',
        content: 'A narrow safe lobe window indicates process instability. Low electrode life suggests cooling or current optimization. Dynamic resistance Fault status requires physical inspection.',
      },
      {
        title: 'Common mistakes',
        content: '**Dynamic resistance min 5 samples**: Fewer than 5 is rejected.\n\n**thickness_ratio < 1**: Error — must be ≥ 1.',
      },
      {
        title: 'FAQ',
        content: '**Q: Is the lobe calculation validated against physical experiments?** A: No — it is an analytical model; use as a reference only.\n\n**Q: Can the pulse strategy be used in production?** A: Only as an initial guideline; process engineer approval is required.',
      },
      {
        title: 'Standards and scope',
        content: 'Minimum nugget diameter uses AWS D8.9 reference formula 4√t (informational only).',
      },
      {
        title: 'Limitations',
        content: 'All engineering modules are heuristic or analytical models. None have undergone independent industrial validation.',
      },
      {
        title: 'Related modules',
        content: '**Weld Quality Analysis** — comprehensive quality score\n\n**Taguchi DOE** — structured parameter optimization',
      },
    ],
  },

  // ── M08 Failure Analysis ───────────────────────────────────────────────
  failure: {
    module_id: 'failure',
    title_tr: 'Hata Analizi',
    title_en: 'Failure Analysis',
    version: '1.0.0',
    sections_tr: [
      {
        title: 'Bu modül nedir?',
        content: 'Hata Analizi, verilen proses parametrelerine göre 10 farklı hata modunun olasılıklarını hesaplar. Sistematik kaynak hata nedenlerini anlamak için kullanılır.',
      },
      {
        title: 'Ne zaman kullanılır?',
        content: 'Kalite sorunlarını teşhis ederken veya FMEA çalışmalarına destek verirken kullanın.',
      },
      {
        title: 'Gerekli girdiler',
        content: '**Temel parametreler**: Malzeme ailesi, stack sayısı, kalınlıklar dizisi (min 2), akım/süre/kuvvet/uç çapı\n\n**Önerilen aralıklar**: Akım/süre/kuvvet/uç çapı için min-max değerleri\n\n**Tahmin edilen çekirdek çapı** ve **minimum çekirdek çapı**',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Sol menüden **Hata Analizi** seçin. Parametreleri girin. **Analiz Et** butonuna tıklayın.',
        examples: [
          {
            id: 'failure_mild_2t',
            label: 'Mild Steel 2T — hata olasılığı analizi',
            inputs: {
              material_family: 'mild_steel',
              stack_count: '2T',
              coated: false,
              adhesive: false,
              shunt_risk: false,
              thicknesses_mm: [1.5, 1.5],
              current_ka: 8.0,
              weld_cycles: 12.0,
              force_kn: 3.5,
              tip_diameter_mm: 6.0,
              squeeze_cycles: 10.0,
              hold_cycles: 5.0,
              cooling_flow_lpm: 2.0,
              cooling_temp_c: 20.0,
              recommended_current_min_ka: 6.5,
              recommended_current_max_ka: 9.5,
              recommended_time_min_cycles: 8.0,
              recommended_time_max_cycles: 18.0,
              recommended_force_min_kn: 2.0,
              recommended_force_max_kn: 6.0,
              recommended_tip_min_mm: 5.0,
              recommended_tip_max_mm: 8.0,
              predicted_nugget_mm: 4.9,
              minimum_nugget_mm: 4.9,
            },
            expected_output: '10 hata modu, toplam olasılık ≤ 100%',
          },
        ],
      },
      {
        title: 'Beklenen çıktı',
        content: '10 hata modu ve her birinin yüzde olasılığı. En yüksek olasılıklı mod öne çıkarılır.',
      },
      {
        title: 'Sonucu nasıl yorumlanır?',
        content: 'Yüksek olasılıklı moda göre önlem alın. Elektrot yapışması yüksekse soğutmayı ve uç çapını kontrol edin.',
      },
      {
        title: 'Yaygın hatalar',
        content: '**thicknesses_mm minimum 2**: Dizi en az 2 eleman içermelidir.',
      },
      {
        title: 'SSS',
        content: '**S: Olasılıklar deneysel veriye dayanıyor mu?** C: Hayır, model heuristik ve parametrik kurallara dayanır. Kalibre edilmiş endüstriyel veri yoktur.',
      },
      {
        title: 'Standartlar',
        content: 'Bu modül herhangi bir endüstriyel standart için doğrulanmış uyumluluk belgesi üretmez.',
      },
      {
        title: 'Sınırlamalar',
        content: 'Olasılıklar ampirik olarak kalibre edilmemiştir. Referans pusula olarak kullanın, karar delili olarak değil.',
      },
      {
        title: 'İlgili modüller',
        content: '**Kaynak Kalite** — genel kalite skoru ve uyumluluk\n\n**Kaynak Lobu** — parametrenin güvenli penceresini görselleştir',
      },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'Failure Analysis computes the probability of 10 distinct failure modes for given process parameters.' },
      { title: 'When should I use it?', content: 'Use during quality troubleshooting or to support FMEA studies.' },
      {
        title: 'Required inputs',
        content: '**Core parameters**: material family, stack count, thicknesses array (min 2), current/time/force/tip\n\n**Recommended ranges**: min-max for current/time/force/tip\n\n**Predicted and minimum nugget diameters**',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Failure Analysis** from the left menu. Enter parameters. Click **Analyze**.',
        examples: [
          {
            id: 'failure_mild_2t',
            label: 'Mild Steel 2T — failure probability analysis',
            inputs: {
              material_family: 'mild_steel', stack_count: '2T', coated: false,
              adhesive: false, shunt_risk: false, thicknesses_mm: [1.5, 1.5],
              current_ka: 8.0, weld_cycles: 12.0, force_kn: 3.5, tip_diameter_mm: 6.0,
              squeeze_cycles: 10.0, hold_cycles: 5.0, cooling_flow_lpm: 2.0, cooling_temp_c: 20.0,
              recommended_current_min_ka: 6.5, recommended_current_max_ka: 9.5,
              recommended_time_min_cycles: 8.0, recommended_time_max_cycles: 18.0,
              recommended_force_min_kn: 2.0, recommended_force_max_kn: 6.0,
              recommended_tip_min_mm: 5.0, recommended_tip_max_mm: 8.0,
              predicted_nugget_mm: 4.9, minimum_nugget_mm: 4.9,
            },
            expected_output: '10 failure modes returned, total probability ≤ 100%',
          },
        ],
      },
      { title: 'Expected output', content: '10 failure modes with percentage probabilities. The top failure mode is highlighted.' },
      { title: 'How to interpret the result', content: 'Take corrective action based on the highest-probability mode. If electrode sticking is high, check cooling and tip diameter.' },
      { title: 'Common mistakes', content: '**thicknesses_mm minimum 2**: The array must have at least 2 elements.' },
      { title: 'FAQ', content: '**Q: Are probabilities based on empirical data?** A: No — the model uses heuristic and parametric rules. No calibrated industrial dataset was used.' },
      { title: 'Standards and scope', content: 'This module does not produce validated compliance certificates for any industrial standard.' },
      { title: 'Limitations', content: 'Probabilities are not empirically calibrated. Use as a reference compass, not a decision proof.' },
      { title: 'Related modules', content: '**Weld Quality Analysis** — overall quality score\n\n**Weld Lobe Lab** — visualize the safe parameter window' },
    ],
  },

  // ── M10 Statistical Analysis ──────────────────────────────────────────
  statistical: {
    module_id: 'statistical',
    title_tr: 'Taguchi DOE ve ANOVA',
    title_en: 'Taguchi DOE & ANOVA',
    version: '1.0.0',
    sections_tr: [
      {
        title: 'Bu modül nedir?',
        content: 'İstatistiksel Analiz modülü Taguchi ortogonal dizi tasarımı ve tek-faktörlü ANOVA sunar. Kaynak parametrelerinin çekirdek çapı üzerindeki etkisini yapılandırılmış deneyler aracılığıyla araştırmanıza olanak verir.',
      },
      {
        title: 'Ne zaman kullanılır?',
        content: 'Parametrelerin etkisini anlayıp optimize etmek istediğinizde; az sayıda deney ile en önemli faktörleri belirlemek için kullanın.',
      },
      {
        title: 'Gerekli girdiler',
        content: '**Taguchi Design**: Dizi tipi (L4/L9/L16/L27), faktörler ve seviyeleri\n\n**Taguchi Analyze**: Design girdisi + deney sonuçları (bir yanıt değeri/run)\n\n**ANOVA**: Gruplar (her grup için değerler listesi), anlamlılık düzeyi',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Soldaki menüden **Taguchi DOE** seçin.\n\nDizi tipini seçin (L9 önerilir, 3 faktör × 3 seviye).\n\nFaktörlerinizi tanımlayın.\n\n**Dizi Oluştur** butonuna tıklayın.\n\nFiziksel deneyleri yapın, yanıt değerlerini girin.\n\n**Analiz Et** butonuna tıklayın.',
        examples: [
          {
            id: 'taguchi_l9_3factor',
            label: 'L9 — 3 faktör: Akım, Süre, Kuvvet',
            inputs: {
              array_type: 'L9',
              factors: [
                { name: 'Current', unit: 'kA', levels: [7.0, 9.0, 11.0] },
                { name: 'WeldTime', unit: 'cycles', levels: [8.0, 12.0, 16.0] },
                { name: 'Force', unit: 'kN', levels: [2.5, 3.5, 4.5] },
              ],
            },
            expected_output: '9 run, her run için faktör değerleri',
          },
        ],
      },
      {
        title: 'Beklenen çıktı',
        content: '**Design**: 9 run (L9), faktör değerleri\n\n**Analyze**: Grand mean, optimal seviyeler, S/N oranları, ANOVA tablosu\n\n**ANOVA**: F istatistiği, p değeri, her grup için ortalama',
      },
      {
        title: 'Sonucu nasıl yorumlanır?',
        content: 'Yüksek S/N oranlı faktörler en etkilidir. p < 0.05 faktörün anlamlı etkisini gösterir. Optimal seviyeler additive modelle tahmin edilir, fiziksel doğrulama gerekir.',
      },
      {
        title: 'Yaygın hatalar',
        content: 'L9 için tam olarak 3 faktör ve 3 seviye gereklidir. L4 ise 2 faktör ve 2 seviye ister.',
      },
      {
        title: 'SSS',
        content: '**S: Additive model optimum daima fiziksel deney ile uyuşur mu?** C: Hayır — doğrulama deneyi şarttır.',
      },
      {
        title: 'Standartlar',
        content: 'Taguchi metodolojisi endüstride yaygın kullanılan bir DOE yaklaşımıdır. Bu yazılım ISO veya ASTM sertifikasyonu üretmez.',
      },
      {
        title: 'Sınırlamalar',
        content: 'Sadece L4/L9/L16/L27 ortogonal diziler desteklenmektedir. Yanıt yüzey modeli (RSM) bu modülde yoktur.',
      },
      {
        title: 'İlgili modüller',
        content: '**Kaynak Kalite** — parametre değerlendirmesi\n\n**Enerji** — enerji-verimlilik optimizasyonu',
      },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'The Statistical Analysis module provides Taguchi orthogonal array design and one-way ANOVA. It supports structured investigation of welding parameter effects on nugget diameter.' },
      { title: 'When should I use it?', content: 'Use when you want to understand and optimize parameter effects, identifying the most important factors with minimal experiments.' },
      {
        title: 'Required inputs',
        content: '**Taguchi Design**: Array type (L4/L9/L16/L27), factors and their levels\n\n**Taguchi Analyze**: Design inputs + experiment results (one response value per run)\n\n**ANOVA**: Groups (list of values per group), significance level',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Taguchi DOE** from the left menu.\n\nChoose array type (L9 recommended for 3 factors × 3 levels).\n\nDefine your factors.\n\nClick **Generate Array**.\n\nConduct physical experiments, enter response values.\n\nClick **Analyze**.',
        examples: [
          {
            id: 'taguchi_l9_3factor',
            label: 'L9 — 3 factors: Current, WeldTime, Force',
            inputs: {
              array_type: 'L9',
              factors: [
                { name: 'Current', unit: 'kA', levels: [7.0, 9.0, 11.0] },
                { name: 'WeldTime', unit: 'cycles', levels: [8.0, 12.0, 16.0] },
                { name: 'Force', unit: 'kN', levels: [2.5, 3.5, 4.5] },
              ],
            },
            expected_output: '9 runs with factor values',
          },
        ],
      },
      { title: 'Expected output', content: '**Design**: 9 runs (L9), factor values per run\n\n**Analyze**: Grand mean, optimal levels, S/N ratios, ANOVA table\n\n**ANOVA**: F-statistic, p-value, group means' },
      { title: 'How to interpret the result', content: 'Factors with high S/N ratio deltas are most influential. p < 0.05 means statistically significant effect. Optimal levels are additive model predictions — always confirm with a verification experiment.' },
      { title: 'Common mistakes', content: 'L9 requires exactly 3 factors with 3 levels each. L4 requires 2 factors with 2 levels.' },
      { title: 'FAQ', content: '**Q: Does the additive model optimal always match a physical experiment?** A: No — a confirmation run is mandatory.' },
      { title: 'Standards and scope', content: 'Taguchi methodology is a widely used DOE approach in industry. This software does not produce ISO or ASTM certifications.' },
      { title: 'Limitations', content: 'Only L4/L9/L16/L27 orthogonal arrays are supported. Response Surface Methodology (RSM) is not included.' },
      { title: 'Related modules', content: '**Weld Quality Analysis** — parameter assessment\n\n**Energy Intelligence** — energy-efficiency optimization' },
    ],
  },

  // ── M11 Energy Intelligence ───────────────────────────────────────────
  energy: {
    module_id: 'energy',
    title_tr: 'Enerji Zekası',
    title_en: 'Energy Intelligence',
    version: '1.0.0',
    sections_tr: [
      { title: 'Bu modül nedir?', content: 'Enerji Zekası, dirençli punta kaynağının enerji tüketimini, spot başına maliyeti ve çoklu-spot agregasyonlarını hesaplar.' },
      { title: 'Ne zaman kullanılır?', content: 'Enerji verimliliği analizi, maliyet tahmini veya senaryo karşılaştırması yaparken kullanın.' },
      {
        title: 'Gerekli girdiler',
        content: '**Tahmin**: resistance_mohm, current_ka, weld_time_ms, efficiency_pct\n\n**Pencere**: Ek endikör hesabı için genişletilmiş parametreler\n\n**Maliyet**: Enerji birim fiyatı, çalışma saati\n\n**Agregasyon**: Birden fazla kaynak noktası parametresi',
      },
      {
        title: 'Adım adım kullanım',
        content: 'Sol menüden **Enerji** seçin. İstediğiniz alt hesabı seçin. Parametreleri girin ve hesaplayın.',
        examples: [
          {
            id: 'energy_estimate_mild',
            label: 'Enerji Tahmini — 100mΩ 8kA 150ms',
            inputs: { resistance_mohm: 100.0, current_ka: 8.0, weld_time_ms: 150.0, efficiency_pct: 100.0 },
            expected_output: 'energy_j ≈ 960 J (I²Rt formülü)',
          },
        ],
      },
      { title: 'Beklenen çıktı', content: 'I²Rt enerji (J), kWh, spot başına maliyet, pencere indikatörleri, dashboard kartları.' },
      { title: 'Sonucu nasıl yorumlanır?', content: 'Oracle formülü: E = I² × R × t. Uygulama bu formülü kullanır, %1 tolerans içinde olmalıdır.' },
      { title: 'Yaygın hatalar', content: '**resistance_mohm=0**: Hata — pozitif değer gereklidir.' },
      { title: 'SSS', content: '**S: Maliyet hesabı canlı döviz kurunu kullanıyor mu?** C: Hayır, sabit bir katsayı kullanılır.' },
      { title: 'Standartlar', content: 'Enerji hesabı I²Rt fizik formülüne dayanır. Ekonomik parametreler kullanıcı girdisidir.' },
      { title: 'Sınırlamalar', content: 'Verimlilik kaybı modeli basitleştirilmiştir. Gerçek güç kayıpları için ölçüm gereklidir.' },
      { title: 'İlgili modüller', content: '**Kaynak Kalite** — parametre kalitesi\n\n**Taguchi DOE** — enerji-performans dengesi optimizasyonu' },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'Energy Intelligence computes resistance spot welding energy consumption, cost per spot, and multi-spot aggregations.' },
      { title: 'When should I use it?', content: 'Use for energy efficiency analysis, cost estimation, or scenario comparison.' },
      {
        title: 'Required inputs',
        content: '**Estimate**: resistance_mohm, current_ka, weld_time_ms, efficiency_pct\n\n**Window**: Extended parameters for additional indicators\n\n**Cost**: Energy unit price, operating hours\n\n**Aggregation**: Multiple weld point parameters',
      },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Energy Intelligence** from the left menu. Choose the desired calculation. Enter parameters and compute.',
        examples: [
          {
            id: 'energy_estimate_mild',
            label: 'Energy Estimate — 100mΩ 8kA 150ms',
            inputs: { resistance_mohm: 100.0, current_ka: 8.0, weld_time_ms: 150.0, efficiency_pct: 100.0 },
            expected_output: 'energy_j ≈ 960 J (I²Rt formula)',
          },
        ],
      },
      { title: 'Expected output', content: 'I²Rt energy (J), kWh, cost per spot, window indicators, dashboard cards.' },
      { title: 'How to interpret the result', content: 'Oracle formula: E = I² × R × t. The application uses this formula; results should be within 1% tolerance.' },
      { title: 'Common mistakes', content: '**resistance_mohm=0**: Error — a positive value is required.' },
      { title: 'FAQ', content: '**Q: Does cost calculation use live exchange rates?** A: No — a fixed coefficient is used.' },
      { title: 'Standards and scope', content: 'Energy calculation is based on the I²Rt physics formula. Economic parameters are user inputs.' },
      { title: 'Limitations', content: 'Efficiency loss model is simplified. Real power losses require measurement.' },
      { title: 'Related modules', content: '**Weld Quality Analysis** — parameter quality\n\n**Taguchi DOE** — energy-performance trade-off optimization' },
    ],
  },

  // ── M12 Static Inspection ──────────────────────────────────────────────
  inspection: {
    module_id: 'inspection',
    title_tr: 'Statik Görsel Muayene',
    title_en: 'Static Inspection',
    version: '1.0.0',
    sections_tr: [
      { title: 'Bu modül nedir?', content: 'Statik Görsel Muayene, yüklenen görüntüde yüzey bulguları (çatlak, spatter, renk bozulması) için otomatik analiz yapar. Bu bir prototip yazılımdır.' },
      { title: 'Ne zaman kullanılır?', content: 'Kaynak yüzeyinin ön incelemesi için kullanın. Sonuçlar, uzman mühendis değerlendirmesini tamamlayıcı niteliktedir.' },
      { title: 'Gerekli girdiler', content: 'PNG veya JPG formatında kaynak yüzeyi görüntüsü. Dosya boyutu sınırına dikkat edin.' },
      {
        title: 'Adım adım kullanım',
        content: 'Sol menüden **Statik Muayene** seçin. Görüntü yükle butonuna tıklayın. PNG/JPG seçin. **Analiz Et** butonuna tıklayın.',
        examples: [
          {
            id: 'static_synth_normal',
            label: 'Sentetik normal kaynak görüntüsü',
            inputs: { _note: 'Lütfen frontend/public/fixtures/swp-test-weld-surface.png yükleyin' },
            expected_output: 'Bulgu yok veya düşük güven skoru, quality_score > 50',
          },
        ],
      },
      { title: 'Beklenen çıktı', content: 'defect_findings listesi (tip, güven skoru), quality_score (0–100), anotasyon önerileri.' },
      { title: 'Sonucu nasıl yorumlanır?', content: 'Yüksek güven skoru ile bulunan bulgular öncelikli inceleme gerektirir. quality_score < 50 mühendis değerlendirmesi önerir.' },
      { title: 'Yaygın hatalar', content: 'Desteklenmeyen dosya formatı (PDF, TIFF vb.) reddedilir. Çok küçük dosyalar analiz kalitesini düşürür.' },
      { title: 'SSS', content: '**S: Bu modül çekirdek çapını ölçer mi?** C: Hayır — yüzey bulgusu tespiti yapar. Çekirdek çapı destructive testle ölçülür.' },
      { title: 'Standartlar', content: 'Bu modül herhangi bir NDT standardı (AWS, ISO 23278 vb.) için sertifikalı değildir.' },
      { title: 'Sınırlamalar', content: 'Protitip yazılımdır. Kalibrasyon verisi sınırlıdır. Endüstriyel bağımsız doğrulama yapılmamıştır.' },
      { title: 'İlgili modüller', content: '**Anotasyon** — yüklenen görüntüleri etiketle\n\n**Canlı İzleme** — gerçek zamanlı görüntü analizi' },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'Static Inspection performs automated surface finding analysis (cracks, spatter, discoloration) on an uploaded image. This is a prototype software.' },
      { title: 'When should I use it?', content: 'Use for preliminary weld surface review. Results are supplementary to expert engineer evaluation.' },
      { title: 'Required inputs', content: 'PNG or JPG weld surface image. Respect the file size limit.' },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Static Inspection** from the left menu. Click the upload button. Select PNG/JPG. Click **Analyze**.',
        examples: [
          {
            id: 'static_synth_normal',
            label: 'Synthetic normal weld surface image',
            inputs: { _note: 'Upload frontend/public/fixtures/swp-test-weld-surface.png' },
            expected_output: 'No findings or low-confidence score, quality_score > 50',
          },
        ],
      },
      { title: 'Expected output', content: 'defect_findings list (type, confidence score), quality_score (0–100), annotation suggestions.' },
      { title: 'How to interpret the result', content: 'High-confidence findings need priority inspection. quality_score < 50 recommends engineer review.' },
      { title: 'Common mistakes', content: 'Unsupported file formats (PDF, TIFF, etc.) are rejected. Very small files reduce analysis quality.' },
      { title: 'FAQ', content: '**Q: Does this module measure nugget diameter?** A: No — it detects surface findings. Nugget diameter is measured by destructive testing.' },
      { title: 'Standards and scope', content: 'This module is NOT certified to any NDT standard (AWS, ISO 23278, etc.).' },
      { title: 'Limitations', content: 'Prototype software. Limited calibration data. No independent industrial validation performed.' },
      { title: 'Related modules', content: '**Annotation** — label uploaded images\n\n**Live Monitoring** — real-time image analysis' },
    ],
  },

  // ── M13 Live Monitoring ───────────────────────────────────────────────
  live: {
    module_id: 'live',
    title_tr: 'Canlı İzleme',
    title_en: 'Live Monitoring',
    version: '1.0.0',
    sections_tr: [
      { title: 'Bu modül nedir?', content: 'Canlı İzleme, webcam, RTSP akışı veya video dosyası (tekrar modu) üzerinden gerçek zamanlı kaynak görüntüsü analizi yapar.' },
      { title: 'Ne zaman kullanılır?', content: 'Kaynak sürecini canlı izlemek veya kaydedilmiş videoyu yeniden oynatarak analiz etmek istediğinizde kullanın.' },
      { title: 'Gerekli girdiler', content: '**Kaynak Türü**: Webcam (tarayıcı yetkisi gerekli), RTSP URL veya yerel video dosyası yolu.' },
      {
        title: 'Adım adım kullanım',
        content: 'Sol menüden **Canlı İzleme** seçin.\n\n**Video Dosyası (Tekrar)** seçeneğini seçin.\n\nDosya yolunu girin.\n\nBAŞLAT butonuna tıklayın.\n\n**DOSYA TEKRAR MODU** başlığının göründüğünü doğrulayın.',
      },
      {
        title: 'Beklenen çıktı',
        content: '**FILE REPLAY MODE** başlığı (mavi çerçeve) ve 5 uyarı bildirimi. Gerçek zamanlı analiz için gerçek endüstriyel kamera gereklidir.',
      },
      { title: 'Sonucu nasıl yorumlanır?', content: 'FILE REPLAY MODE sadece yazılım akışını test eder. Gerçek endüstriyel performans iddiaları için gerçek kamera testi şarttır.' },
      { title: 'Yaygın hatalar', content: 'Desteklenmeyen codec veya dosya formatı yüklenirse hata mesajı görünür.' },
      { title: 'SSS', content: '**S: FILE REPLAY MODE gerçek hız kanıtlar mı?** C: Hayır — sadece yazılım akışını test eder. Gerçek kamera performansı ayrıca ölçülmelidir.' },
      { title: 'Standartlar', content: 'Bu modül gerçek zamanlı endüstriyel kamera testleri için sertifikalı değildir.' },
      { title: 'Sınırlamalar', content: 'FILE REPLAY MODE gerçek endüstriyel yüksek hızlı kamera performansını kanıtlamaz. RTSP ve webcam akışları sanal/gerçek kamera altyapısı gerektirir.' },
      { title: 'İlgili modüller', content: '**Statik Muayene** — tek görüntü analizi\n\n**Anotasyon** — görüntü etiketleme' },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'Live Monitoring performs real-time weld image analysis from a webcam, RTSP stream, or video file (replay mode).' },
      { title: 'When should I use it?', content: 'Use to monitor the welding process live, or to replay and analyze recorded video.' },
      { title: 'Required inputs', content: '**Source type**: Webcam (requires browser permission), RTSP URL, or local video file path.' },
      {
        title: 'Step-by-step tutorial',
        content: 'Select **Live Monitoring** from the left menu.\n\nSelect **Video File (Replay)**.\n\nEnter the file path.\n\nClick START.\n\nVerify the **FILE REPLAY MODE** banner appears.',
      },
      {
        title: 'Expected output',
        content: '**FILE REPLAY MODE** banner (blue frame) with 5 disclaimer notices. Real-time industrial analysis requires a real industrial camera.',
      },
      { title: 'How to interpret the result', content: 'FILE REPLAY MODE only tests software flow. Real industrial performance claims require real camera testing.' },
      { title: 'Common mistakes', content: 'Unsupported codec or file format shows an error message.' },
      { title: 'FAQ', content: '**Q: Does FILE REPLAY MODE prove real-time speed?** A: No — it only tests software flow. Real camera performance must be measured separately.' },
      { title: 'Standards and scope', content: 'This module is not certified for real-time industrial camera testing.' },
      { title: 'Limitations', content: 'FILE REPLAY MODE does not prove real industrial high-speed camera performance. RTSP and webcam streams require real camera infrastructure.' },
      { title: 'Related modules', content: '**Static Inspection** — single image analysis\n\n**Annotation** — image labeling' },
    ],
  },

  // ── M09 Model Catalog ─────────────────────────────────────────────────
  models: {
    module_id: 'models',
    title_tr: 'Model Kataloğu',
    title_en: 'Model Catalog',
    version: '1.0.0',
    sections_tr: [
      { title: 'Bu modül nedir?', content: 'Model Kataloğu, SpotWeldPro AI içindeki tüm kayıtlı modelleri, durumlarını, sürümlerini ve kapsam bilgilerini listeler.' },
      { title: 'Ne zaman kullanılır?', content: 'Hangi modelin aktif olduğunu görmek, sürüm geçmişini incelemek veya belirli bir model için korumalı tahmin yapmak istediğinizde kullanın.' },
      { title: 'Gerekli girdiler', content: 'Sadece oturum tokeni. Belirli model tahmini için: model_id.' },
      { title: 'Adım adım kullanım', content: 'Sol menüden **Model Kataloğu** seçin. Listeyi inceleyin. Tahmin için modeli seçin.' },
      { title: 'Beklenen çıktı', content: 'Model listesi (id, ad, sürüm, durum, kapsam) ve seçili model için korumalı tahmin sonucu.' },
      { title: 'Sonucu nasıl yorumlanır?', content: 'ACTIVE durumdaki modeller üretim için değerlendirilebilir. RETIRED modeller sadece referans amaçlıdır.' },
      { title: 'Yaygın hatalar', content: '403: predict-guard için yetki gereklidir. DEMO_USER predict-guard erişimine sahip olmayabilir.' },
      { title: 'SSS', content: '**S: Model nasıl eğitilir?** C: Model eğitimi E1-E4 kalite kapılarından geçmeyi ve Kalite Mühendisi onayını gerektirir. Bu UI\'dan otomatik eğitim yapılamaz.' },
      { title: 'Standartlar', content: 'Model yaşam döngüsü yönetimi için SpotWeldPro AI iç yönetim çerçevesi kullanılmaktadır.' },
      { title: 'Sınırlamalar', content: 'Model eğitim kapısı kapalıdır (training_allowed=False). 175 E1 çakışması Kalite Mühendisi çözümlenmesini bekliyor.' },
      { title: 'İlgili modüller', content: '**Dataset Paneli** — eğitim hazırlık durumu\n\n**Çakışma İnceleme** — E1 çakışma çözümleme' },
    ],
    sections_en: [
      { title: 'What is this module?', content: 'The Model Catalog lists all registered models in SpotWeldPro AI, with their status, version, and scope information.' },
      { title: 'When should I use it?', content: 'Use to see which model is active, review version history, or run a guarded prediction for a specific model.' },
      { title: 'Required inputs', content: 'Only a session token. For specific model prediction: model_id.' },
      { title: 'Step-by-step tutorial', content: 'Select **Model Catalog** from the left menu. Review the list. Select a model for prediction.' },
      { title: 'Expected output', content: 'Model list (id, name, version, status, scope) and guarded prediction result for the selected model.' },
      { title: 'How to interpret the result', content: 'ACTIVE models can be evaluated for production use. RETIRED models are for reference only.' },
      { title: 'Common mistakes', content: '403: predict-guard requires authorization. DEMO_USER may not have predict-guard access.' },
      { title: 'FAQ', content: '**Q: How is a model trained?** A: Model training requires passing E1-E4 quality gates and Quality Engineer approval. Automatic training from this UI is not possible.' },
      { title: 'Standards and scope', content: 'SpotWeldPro AI internal governance framework is used for model lifecycle management.' },
      { title: 'Limitations', content: 'Model training gate is closed (training_allowed=False). 175 E1 conflicts are pending Quality Engineer resolution.' },
      { title: 'Related modules', content: '**Dataset Dashboard** — training readiness status\n\n**Conflict Review** — E1 conflict resolution' },
    ],
  },
}

/** Minimal stubs for remaining modules (annotation, dataset, conflict review, projects) */
const STUB_MODULES: Record<string, { tr: string; en: string; title_tr: string; title_en: string }> = {
  annotation: {
    title_tr: 'Anotasyon',
    title_en: 'Annotation',
    tr: 'Bu modül, yüklenen görüntülere bulgu etiketleri eklemenizi sağlar. DEMO_USER anotasyon oluşturabilir ancak inceleyemez (QUALITY_ENGINEER rolü gereklidir).',
    en: 'This module allows adding finding labels to uploaded images. DEMO_USER can create annotations but cannot review them (QUALITY_ENGINEER role required).',
  },
  dataset_dashboard: {
    title_tr: 'Dataset Paneli',
    title_en: 'Dataset Dashboard',
    tr: 'Annotasyon sayaçlarını ve eğitim hazırlık durumunu gösterir. training_allowed=False — 175 E1 çakışması Kalite Mühendisi çözümlenmesini bekliyor.',
    en: 'Shows annotation counters and training readiness status. training_allowed=False — 175 E1 conflicts are pending Quality Engineer resolution.',
  },
  conflict_review: {
    title_tr: 'Çakışma İnceleme',
    title_en: 'Conflict Review',
    tr: 'E1 anotasyon çakışmalarını çözümlemek için Kalite Mühendisi rolü gereklidir. DEMO_USER bu modüle erişemez (403 PERMISSION_DENIED).',
    en: 'Resolving E1 annotation conflicts requires the Quality Engineer role. DEMO_USER cannot access this module (403 PERMISSION_DENIED).',
  },
  projects: {
    title_tr: 'Projeler ve Kaynak Noktaları',
    title_en: 'Projects & Weld Points',
    tr: 'Projeler oluşturun, düzenleyin, silin. Her projeye kaynak noktaları ekleyin. DEMO_USER kendi projelerini yönetebilir.',
    en: 'Create, edit and delete projects. Add weld points to each project. DEMO_USER can manage their own projects.',
  },
  help: {
    title_tr: 'Yardım Merkezi',
    title_en: 'Help Center',
    tr: 'Genel kullanım rehberi ve SSS. Bu panelin içeriği bu modül için de geçerlidir.',
    en: 'General usage guide and FAQ. The content of this panel also applies to this module.',
  },
}

function makeStub(id: string): ModuleReadContent {
  const s = STUB_MODULES[id]
  if (!s) return makeUnknownStub(id)
  const single_tr: Section = { title: 'Bu modül nedir?', content: s.tr }
  const single_en: Section = { title: 'What is this module?', content: s.en }
  return {
    module_id: id,
    title_tr: s.title_tr,
    title_en: s.title_en,
    version: '1.0.0',
    sections_tr: [single_tr],
    sections_en: [single_en],
  }
}

function makeUnknownStub(id: string): ModuleReadContent {
  return {
    module_id: id,
    title_tr: id,
    title_en: id,
    version: '0.0.0',
    sections_tr: [{ title: 'Bilgi Yok', content: 'Bu modül için yardım içeriği henüz hazırlanmamıştır.' }],
    sections_en: [{ title: 'No Content', content: 'Help content for this module has not been prepared yet.' }],
  }
}

export function getModuleContent(moduleId: string): ModuleReadContent | null {
  if (REGISTRY[moduleId]) return REGISTRY[moduleId]
  if (STUB_MODULES[moduleId]) return makeStub(moduleId)
  return null
}

export function listSupportedModules(): string[] {
  return [...Object.keys(REGISTRY), ...Object.keys(STUB_MODULES)]
}

export default REGISTRY
