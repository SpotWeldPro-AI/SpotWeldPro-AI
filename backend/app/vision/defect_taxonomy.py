"""
VISION-P3D: Spot weld defect taxonomy — bilingual TR/EN.

Covers:
  - All 13 classes from the V5 external dataset (surface-visible defects)
  - 5 additional defect types from welding literature (internal / NDT)

Design rules:
  - Multi-label: a single weld image may exhibit multiple defects simultaneously.
  - Observability distinguishes what a camera can reliably detect from what
    requires destructive testing (cross-section) or NDT (ultrasonic, XRF).
  - surface_classifier_applicable is True ONLY when the defect produces
    reproducible surface visual features that can be learned from labeled images.
  - No model training is permitted until DatasetAudit.is_training_allowed() == True
    and all E1–E4 data quality gates from P3B/P3C are resolved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class DefectCode(str, Enum):
    """Canonical code for every defect class.

    V5 dataset classes use the original Turkish archive keys so that existing
    manifest and label files remain compatible.  Internal-only defects added
    from literature use lowercase English keys.
    """
    # ── Accept class ──────────────────────────────────────────────────────────
    OK = "ok"

    # ── Surface-visible defects (present in V5 dataset) ───────────────────────
    SPATTER = "capak"                   # çapak / spatter-flash
    DEFORMED = "deformeli"              # deformed electrode face impression
    BROKEN = "kopuk"                    # broken / severed weld
    MISSING = "eksik"                   # missing weld point
    SMALL_NUGGET_INDICATOR = "kucuk_cekirdek"  # small indentation; indicator ONLY
    MISALIGNED = "kacik"                # electrode misalignment
    OVERLAPPING = "ust_uste"            # overlapping weld points
    EDGE_WELD = "kenar"                 # weld placed at sheet edge
    BURN_THROUGH = "delik"              # burn-through / hole
    DOUBLE_SHEET = "cift_sac"           # double / extra sheet layer
    CRUSH_DENT = "cokertme"             # crush dent from excessive force
    GENERIC_NOK = "generic_bad"         # generic NOK (non-specific label)

    # ── Internal defects — require cross-section or NDT (not in V5) ──────────
    INCOMPLETE_FUSION = "incomplete_fusion"   # yetersiz kaynak nüfuziyeti
    POROSITY = "porosity"                     # gözenek
    HOT_CRACK = "hot_crack"                   # sıcak çatlak
    EXPULSION = "expulsion"                   # pıskırma / material ejection
    COLD_LAP = "cold_lap"                     # soğuk bindirme


class ObservabilityLevel(str, Enum):
    """
    How reliably a defect can be detected from a surface image.

    SURFACE_VISIBLE    — Produces clear, reproducible surface features; a surface-
                         image classifier can be trained to detect it reliably.
    SURFACE_INDICATOR  — Surface signs exist (e.g. discolouration, small indentation)
                         but their absence does NOT rule out the defect; internal
                         confirmation (NDT or cross-section) is required for final
                         pass/fail.
    NDT_REQUIRED       — Surface appears normal; requires ultrasonic, radiographic,
                         or other non-destructive testing.  Surface classifiers
                         cannot detect this defect.
    DESTRUCTIVE_ONLY   — Only visible after metallographic sectioning.  Surface and
                         NDT both cannot reliably detect it.  Label source must be
                         DESTRUCTIVE_TEST.
    """
    SURFACE_VISIBLE = "SURFACE_VISIBLE"
    SURFACE_INDICATOR = "SURFACE_INDICATOR"
    NDT_REQUIRED = "NDT_REQUIRED"
    DESTRUCTIVE_ONLY = "DESTRUCTIVE_ONLY"


class DefectSeverity(str, Enum):
    """
    Severity classification aligned with ISO 15614-12 and OEM standards.

    CRITICAL — Automatic rejection; potential structural failure.
    HIGH     — Reject; requires engineer review and disposition.
    MEDIUM   — Context-dependent; check application standard.
    LOW      — Flag for monitoring; may be within tolerance by standard.
    ACCEPT   — Weld meets acceptance criteria; not a defect.
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ACCEPT = "ACCEPT"


@dataclass
class TaxonomyEntry:
    """
    Single entry in the defect taxonomy.

    Fields:
      code                      Canonical DefectCode key.
      name_tr                   Turkish defect name.
      name_en                   English defect name.
      description_tr            Turkish description (≤2 sentences).
      description_en            English description (≤2 sentences).
      observability             How detectable this defect is from a surface image.
      severity                  Default severity under OEM / ISO standards.
      visual_indicators         Bullet-list of surface visual signs (observable features).
      requires_cross_section    True if metallographic sectioning is required for
                                definitive confirmation.
      requires_ndt              True if UT / radiographic / other NDT is required.
      in_v5_dataset             True if this class appears in the V5 external dataset.
      surface_classifier_applicable
                                True when a surface-image classifier can LEARN this
                                defect from labeled images.  False for internal defects.
      multi_label_cooccurrence  Codes that commonly appear together with this defect.
      annotation_region         How to draw the annotation: BBOX, POLYGON, POINT, WHOLE_IMAGE.
      notes                     Engineering caveats and training restrictions.
    """
    code: DefectCode
    name_tr: str
    name_en: str
    description_tr: str
    description_en: str
    observability: ObservabilityLevel
    severity: DefectSeverity
    visual_indicators: List[str]
    requires_cross_section: bool
    requires_ndt: bool
    in_v5_dataset: bool
    surface_classifier_applicable: bool
    multi_label_cooccurrence: List[DefectCode] = field(default_factory=list)
    annotation_region: str = "BBOX"   # BBOX | POLYGON | POINT | WHOLE_IMAGE
    notes: List[str] = field(default_factory=list)

    def is_internal_only(self) -> bool:
        """True when the defect is not reliably detectable from surface images."""
        return self.observability in (
            ObservabilityLevel.NDT_REQUIRED,
            ObservabilityLevel.DESTRUCTIVE_ONLY,
        )

    def requires_physical_confirmation(self) -> bool:
        """True when NDT or cross-section is required for a definitive verdict."""
        return self.requires_cross_section or self.requires_ndt


# ── Taxonomy registry ──────────────────────────────────────────────────────────

TAXONOMY: Dict[DefectCode, TaxonomyEntry] = {

    DefectCode.OK: TaxonomyEntry(
        code=DefectCode.OK,
        name_tr="Kabul",
        name_en="Accepted",
        description_tr="Kaynak noktası görsel incelemede kabul kriterlerini karşılıyor.",
        description_en="Weld point meets acceptance criteria on visual inspection.",
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.ACCEPT,
        visual_indicators=[
            "Uniform, circular electrode indentation",
            "No visible spatter, cracks, or surface discontinuities",
            "Indentation diameter consistent with electrode face geometry",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        annotation_region="WHOLE_IMAGE",
        notes=[
            "SURFACE_OBSERVATION labels only — does not confirm nugget diameter.",
            "A visually OK weld may still have an undersized nugget; "
            "metallographic cross-section or UT is required for nugget acceptance.",
        ],
    ),

    DefectCode.SPATTER: TaxonomyEntry(
        code=DefectCode.SPATTER,
        name_tr="Çapak / Kaynak Sıçraması",
        name_en="Spatter / Flash",
        description_tr=(
            "Kaynak sırasında elektrodlar arasından dışarı fırlayan ergimiş metal "
            "parçacıkları.  Sac yüzeyi veya elektrod yüzeyinde katılaşmış metal damlacıkları "
            "olarak görünür."
        ),
        description_en=(
            "Molten metal particles ejected during welding, visible as solidified "
            "droplets on the sheet or electrode face surface."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.MEDIUM,
        visual_indicators=[
            "Bright metallic droplets scattered around the weld point",
            "Ring of solidified spatter at varying radii from weld centre",
            "May include discolouration from heat",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.BURN_THROUGH, DefectCode.EXPULSION],
        annotation_region="POLYGON",
        notes=[
            "V5 dataset: 112 samples — largest specific-defect class after generic_bad.",
            "Spatter presence does not confirm nugget quality; a weld with spatter "
            "may still have acceptable nugget if process parameters are corrected.",
            "V5 annotation contamination: 71% MEDIUM or HIGH; ROI crop recommended.",
        ],
    ),

    DefectCode.DEFORMED: TaxonomyEntry(
        code=DefectCode.DEFORMED,
        name_tr="Deformeli Elektrod İzi",
        name_en="Deformed Electrode Impression",
        description_tr=(
            "Elektrod yüzeyindeki aşınma veya hasar nedeniyle kaynak noktasında "
            "beklenen dairesel iz yerine düzensiz bir şekil oluşur."
        ),
        description_en=(
            "Irregular or asymmetric electrode impression caused by electrode wear or "
            "damage, producing a non-circular weld footprint."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Non-circular or asymmetric indentation on sheet surface",
            "Partial or double impression",
            "May show electrode face pitting or mushrooming pattern",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.MISALIGNED, DefectCode.SMALL_NUGGET_INDICATOR],
        annotation_region="BBOX",
        notes=[
            "V5 dataset: 54 samples; 50 in train, 1 val, 3 test — severe class imbalance.",
            "Electrode wear is a process root cause; this defect indicates electrode "
            "replacement is overdue.",
        ],
    ),

    DefectCode.BROKEN: TaxonomyEntry(
        code=DefectCode.BROKEN,
        name_tr="Kopuk Kaynak",
        name_en="Broken / Severed Weld",
        description_tr=(
            "Kaynak noktası kısmen veya tamamen kopmuş; sac plakalar arasındaki "
            "bağlantı zayıflamış ya da yok olmuştur."
        ),
        description_en=(
            "Weld nugget partially or fully detached; the inter-sheet bond is "
            "weakened or absent."
        ),
        observability=ObservabilityLevel.SURFACE_INDICATOR,
        severity=DefectSeverity.CRITICAL,
        visual_indicators=[
            "Visible fracture line or crack at the weld periphery",
            "Sheet separation visible under light loading",
            "Distorted or absent electrode indentation",
        ],
        requires_cross_section=True,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.MISSING],
        annotation_region="BBOX",
        notes=[
            "Surface appearance alone may not distinguish partial break from full break; "
            "peel or chisel test required for definitive confirmation.",
            "Automatic reject in all automotive OEM standards.",
        ],
    ),

    DefectCode.MISSING: TaxonomyEntry(
        code=DefectCode.MISSING,
        name_tr="Eksik Kaynak",
        name_en="Missing Weld",
        description_tr=(
            "Kaynak noktası hiç yapılmamış veya programlama hatası sonucunda "
            "atlanan bir kaynak noktası."
        ),
        description_en=(
            "Weld point was not performed; electrode indentation absent at the "
            "planned weld location."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.CRITICAL,
        visual_indicators=[
            "No electrode indentation visible at expected weld location",
            "Sheet surface undisturbed; no heat-affected zone",
            "Adjacent welds present but this location skipped",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        annotation_region="POINT",
        notes=[
            "High confidence surface detection: absence of indentation is unambiguous.",
            "Root cause: robot program skip, PLC error, or offline production.",
        ],
    ),

    DefectCode.SMALL_NUGGET_INDICATOR: TaxonomyEntry(
        code=DefectCode.SMALL_NUGGET_INDICATOR,
        name_tr="Küçük Çekirdek Göstergesi",
        name_en="Small Nugget Indicator (Surface)",
        description_tr=(
            "Elektrod izi normalden küçük görünüyor; bu durum yetersiz nugget çapına "
            "işaret edebilir.  Ancak iz boyutu tek başına nugget kalitesini kanıtlamaz."
        ),
        description_en=(
            "Electrode indentation appears smaller than nominal; this is a surface "
            "indicator of potential undersized nugget but does NOT confirm it without "
            "metallographic cross-section."
        ),
        observability=ObservabilityLevel.SURFACE_INDICATOR,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Indentation diameter visibly smaller than the electrode face diameter",
            "Shallow, faint, or barely visible impression",
            "Unusually small heat-affected zone",
        ],
        requires_cross_section=True,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.DEFORMED],
        annotation_region="BBOX",
        notes=[
            "CRITICAL CAUTION: 'kucuk_cekirdek' in V5 is labeled by SURFACE_OBSERVATION "
            "only.  A small surface impression does not confirm nugget undersizing; "
            "the nugget may be adequate if electrode contact diameter is acceptable.",
            "V5 class imbalance: 4 train / 22 test — anomalous split; model cannot "
            "learn this class reliably from V5 alone.",
            "For nugget diameter acceptance, destructive testing (cross-section + "
            "caliper measurement) or UT is required regardless of surface appearance.",
        ],
    ),

    DefectCode.MISALIGNED: TaxonomyEntry(
        code=DefectCode.MISALIGNED,
        name_tr="Kaçık Kaynak / Hizalama Hatası",
        name_en="Misaligned Weld",
        description_tr=(
            "Kaynak noktası planlanan konumdan yatay olarak kaymış; elektrod izi "
            "hedef konumun dışına taşmış."
        ),
        description_en=(
            "Weld point laterally displaced from the planned position; electrode "
            "indentation is offset from the target location."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Electrode indentation visibly offset from weld symbol or reference mark",
            "Indentation partially on sheet edge or flange boundary",
            "Weld sequence spacing inconsistent with adjacent points",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.EDGE_WELD, DefectCode.DEFORMED],
        annotation_region="BBOX",
        notes=[
            "Severity depends on displacement magnitude; edge proximity increases risk.",
            "May coexist with edge weld (kenar) when displacement is toward sheet edge.",
        ],
    ),

    DefectCode.OVERLAPPING: TaxonomyEntry(
        code=DefectCode.OVERLAPPING,
        name_tr="Üst Üste Kaynak",
        name_en="Overlapping Weld",
        description_tr=(
            "İki kaynak noktası birbirine çok yakın yapılmış veya üst üste binmiş; "
            "birinin ısı etki bölgesi diğerinin kaynak bölgesini etkiliyor."
        ),
        description_en=(
            "Two weld points placed too close together or overlapping; the heat-affected "
            "zone of one intrudes on the nugget zone of the other."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.MEDIUM,
        visual_indicators=[
            "Two electrode impressions partially or fully overlapping",
            "Shared heat-affected zone discolouration",
            "Distorted nugget boundary visible at the overlap",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        annotation_region="BBOX",
        notes=[
            "V5 class imbalance: 2 train / 3 test — insufficient for classifier training.",
            "Severity depends on OEM spacing standard (typically min d = 3×√t or 4×√t).",
        ],
    ),

    DefectCode.EDGE_WELD: TaxonomyEntry(
        code=DefectCode.EDGE_WELD,
        name_tr="Kenar Kaynağı",
        name_en="Edge Weld",
        description_tr=(
            "Kaynak noktası sac kenarına çok yakın yapılmış; kenar bölgesindeki "
            "malzeme azlığı nedeniyle nugget oluşumu bozulmuş olabilir."
        ),
        description_en=(
            "Weld placed too close to the sheet edge; reduced material at the edge "
            "may impair nugget formation and structural integrity."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Electrode indentation within minimum edge distance",
            "Partial nugget impression — one side truncated by sheet edge",
            "Visible sheet deformation or tear at edge",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.MISALIGNED],
        annotation_region="BBOX",
        notes=[
            "Minimum edge distance per OEM standard (typically 1.5–2× nugget diameter).",
        ],
    ),

    DefectCode.BURN_THROUGH: TaxonomyEntry(
        code=DefectCode.BURN_THROUGH,
        name_tr="Delik / Yanma Deliği",
        name_en="Burn-Through / Hole",
        description_tr=(
            "Aşırı ısı girişi nedeniyle sac üzerinde delik oluşmuş; malzeme "
            "eriyerek veya dökülerek kaynak bölgesinde boşluk meydana gelmiş."
        ),
        description_en=(
            "Hole formed in the sheet due to excessive heat input; material melted "
            "through, leaving a void at the weld location."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.CRITICAL,
        visual_indicators=[
            "Visible hole or void at weld centre",
            "Molten material residue around hole perimeter",
            "Severe discolouration and surface oxidation",
            "May coexist with heavy spatter",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.SPATTER, DefectCode.EXPULSION],
        annotation_region="POLYGON",
        notes=[
            "Automatic reject in all automotive OEM standards.",
            "Root cause: excessive welding current, too-long squeeze time, or "
            "contaminated electrode.",
        ],
    ),

    DefectCode.DOUBLE_SHEET: TaxonomyEntry(
        code=DefectCode.DOUBLE_SHEET,
        name_tr="Çift Sac / Fazladan Tabaka",
        name_en="Double Sheet / Extra Layer",
        description_tr=(
            "Kaynak bölgesinde planlananın üstünde bir sac tabakası daha bulunuyor; "
            "bu durum aynı konumda gereksiz bir kaynak yapılmasına neden olur."
        ),
        description_en=(
            "An unintended extra sheet layer present at the weld location; causes "
            "redundant or misapplied welding at that position."
        ),
        observability=ObservabilityLevel.SURFACE_INDICATOR,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Elevated or stepped sheet surface at weld zone",
            "Unusual electrode impression depth or shape",
            "Visible sheet lap joint where only single-sheet expected",
        ],
        requires_cross_section=True,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        annotation_region="BBOX",
        notes=[
            "Surface indicator only — extra layer may not always be visible from above.",
            "V5 dataset: only 14 samples; 10 train, 1 val, 3 test.",
        ],
    ),

    DefectCode.CRUSH_DENT: TaxonomyEntry(
        code=DefectCode.CRUSH_DENT,
        name_tr="Çökürtme / Ezilme",
        name_en="Crush Dent",
        description_tr=(
            "Aşırı elektrod basıncı nedeniyle sac yüzeyinde çöküntü oluşmuş; "
            "malzeme incelmesi ve yapısal zayıflama riski var."
        ),
        description_en=(
            "Sheet surface depressed due to excessive electrode force; risk of "
            "material thinning and structural weakening."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.MEDIUM,
        visual_indicators=[
            "Deeper-than-nominal indentation",
            "Sheet surface visibly concave around weld point",
            "Potential cracking at the dent perimeter",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=True,
        annotation_region="BBOX",
        notes=[
            "V5 dataset: only 4 samples — insufficient for classifier training (all in train, "
            "0 test samples).",
            "Severity depends on depth relative to sheet thickness.",
        ],
    ),

    DefectCode.GENERIC_NOK: TaxonomyEntry(
        code=DefectCode.GENERIC_NOK,
        name_tr="Genel Hatalı (Tanımsız Hata)",
        name_en="Generic NOK (Unspecified Defect)",
        description_tr=(
            "Kaynak noktası görsel incelemede reddedilmiş ancak spesifik hata türü "
            "kaydedilmemiş.  Bu etiket, spesifik hata sınıflarının mevcut olmadığı "
            "arşiv kaynaklarından (Puntanok_1/2.zip) gelmektedir."
        ),
        description_en=(
            "Weld rejected on visual inspection but specific defect type not recorded. "
            "This label originates from generic NOK archives (Puntanok_1/2.zip) where "
            "specific defect classification was not performed."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.HIGH,
        visual_indicators=["Visible defect of unspecified type"],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=True,
        surface_classifier_applicable=False,
        annotation_region="WHOLE_IMAGE",
        notes=[
            "TRAINING RESTRICTION: surface_classifier_applicable=False because this "
            "label conflates multiple specific defect types.  Using it for classifier "
            "training would dilute class-specific features.",
            "P3C finding: 173 label-conflict pairs between generic_bad and specific-defect "
            "classes — the same image appears in both archives.",
            "Preferred remediation: replace each generic_bad duplicate with its specific "
            "defect label from Punta_hatalar_1/2.zip (see DATASET_CLEANING_REPORT.md).",
        ],
    ),

    # ── Internal defects (not in V5; from welding literature) ─────────────────

    DefectCode.INCOMPLETE_FUSION: TaxonomyEntry(
        code=DefectCode.INCOMPLETE_FUSION,
        name_tr="Yetersiz Kaynak Nüfuziyeti",
        name_en="Incomplete Fusion / Cold Weld",
        description_tr=(
            "Elektrodlar arasındaki sac tabakalar tam olarak birleşmemiş; "
            "nugget oluşmamış veya çok küçük kalmış.  Yüzeyden görünmez."
        ),
        description_en=(
            "Sheet layers did not fully fuse; the nugget did not form or is severely "
            "undersized.  Surface appearance may look normal."
        ),
        observability=ObservabilityLevel.DESTRUCTIVE_ONLY,
        severity=DefectSeverity.CRITICAL,
        visual_indicators=[
            "No reliable surface indicator — surface may appear normal",
            "Possibly shallow indentation (overlaps with SMALL_NUGGET_INDICATOR)",
        ],
        requires_cross_section=True,
        requires_ndt=True,
        in_v5_dataset=False,
        surface_classifier_applicable=False,
        multi_label_cooccurrence=[DefectCode.SMALL_NUGGET_INDICATOR],
        annotation_region="WHOLE_IMAGE",
        notes=[
            "Cannot be detected by surface image classification.",
            "Detection methods: metallographic cross-section, destructive peel/chisel "
            "test, or ultrasonic testing.",
            "This is the most dangerous defect in resistance spot welding — a structurally "
            "failed weld with normal-looking surface.",
            "Motivates why SURFACE_OBSERVATION labels are INSUFFICIENT for nugget "
            "acceptance in automotive safety applications.",
        ],
    ),

    DefectCode.POROSITY: TaxonomyEntry(
        code=DefectCode.POROSITY,
        name_tr="Gözenek / İçsel Boşluklar",
        name_en="Porosity / Internal Voids",
        description_tr=(
            "Nugget içinde gaz kabarcıklarından kaynaklanan boşluklar; "
            "kesit alanını azaltarak mekanik dayanımı düşürür."
        ),
        description_en=(
            "Gas voids within the nugget, reducing cross-section area and "
            "mechanical strength."
        ),
        observability=ObservabilityLevel.NDT_REQUIRED,
        severity=DefectSeverity.HIGH,
        visual_indicators=["No reliable surface indicator"],
        requires_cross_section=True,
        requires_ndt=True,
        in_v5_dataset=False,
        surface_classifier_applicable=False,
        annotation_region="WHOLE_IMAGE",
        notes=[
            "Cannot be detected by surface image classification.",
            "Detection: ultrasonic phased-array or radiographic testing.",
        ],
    ),

    DefectCode.HOT_CRACK: TaxonomyEntry(
        code=DefectCode.HOT_CRACK,
        name_tr="Sıcak Çatlak",
        name_en="Hot Crack / Solidification Crack",
        description_tr=(
            "Nugget katılaşması sırasında oluşan çatlak; sıvı metal sınırlarından "
            "başlayarak genişler.  Çoğunlukla nugget merkezinde radyal yönlüdür."
        ),
        description_en=(
            "Crack formed during nugget solidification; initiates at liquid metal "
            "boundaries and propagates radially from the nugget centre."
        ),
        observability=ObservabilityLevel.DESTRUCTIVE_ONLY,
        severity=DefectSeverity.CRITICAL,
        visual_indicators=[
            "Possibly visible as a fine surface crack if crack propagates to surface "
            "(rare; usually fully internal)",
        ],
        requires_cross_section=True,
        requires_ndt=True,
        in_v5_dataset=False,
        surface_classifier_applicable=False,
        annotation_region="WHOLE_IMAGE",
        notes=[
            "Cannot be reliably detected by surface image classification.",
            "Common in high-carbon or galvanized steel.",
            "Detection: metallographic cross-section; sometimes visible under SEM.",
        ],
    ),

    DefectCode.EXPULSION: TaxonomyEntry(
        code=DefectCode.EXPULSION,
        name_tr="Pıskırma / Eriyik Metal Fırlaması",
        name_en="Expulsion / Molten Metal Ejection",
        description_tr=(
            "Kaynak sırasında sıvı metalin elektrod-sac arayüzünden dışarı "
            "fırlaması; genellikle görsel olarak gözlemlenebilir."
        ),
        description_en=(
            "Ejection of molten metal from the electrode-sheet interface during "
            "welding; usually produces visible surface evidence."
        ),
        observability=ObservabilityLevel.SURFACE_VISIBLE,
        severity=DefectSeverity.HIGH,
        visual_indicators=[
            "Visible molten metal traces or channels on sheet surface",
            "Heavily oxidised or discoloured zone around weld",
            "May leave impact craters or radial splash patterns",
        ],
        requires_cross_section=False,
        requires_ndt=False,
        in_v5_dataset=False,
        surface_classifier_applicable=True,
        multi_label_cooccurrence=[DefectCode.SPATTER, DefectCode.BURN_THROUGH],
        annotation_region="POLYGON",
        notes=[
            "Not in V5 dataset — no labeled training data available.",
            "Visually similar to spatter (capak) but typically more severe and larger.",
            "Expulsion causes nugget material loss; cross-section recommended to "
            "confirm residual nugget diameter.",
        ],
    ),

    DefectCode.COLD_LAP: TaxonomyEntry(
        code=DefectCode.COLD_LAP,
        name_tr="Soğuk Bindirme",
        name_en="Cold Lap / Lack of Bonding",
        description_tr=(
            "Nugget sınırında sac tabakalar arasında bağlantı oluşmamış; "
            "nugget çevresi yetersiz füzyona sahip ancak merkezi normal görünüyor."
        ),
        description_en=(
            "Lack of bonding at the nugget periphery; sheets are not fused at "
            "the nugget boundary despite apparently normal nugget centre."
        ),
        observability=ObservabilityLevel.DESTRUCTIVE_ONLY,
        severity=DefectSeverity.HIGH,
        visual_indicators=["No reliable surface indicator"],
        requires_cross_section=True,
        requires_ndt=True,
        in_v5_dataset=False,
        surface_classifier_applicable=False,
        annotation_region="WHOLE_IMAGE",
        notes=[
            "Cannot be detected by surface image classification.",
            "May reduce dynamic load capacity without affecting static strength.",
        ],
    ),
}


# ── Accessor functions ─────────────────────────────────────────────────────────

def get_taxonomy_entry(code: DefectCode) -> TaxonomyEntry:
    """Return the taxonomy entry for a defect code.  Raises KeyError if unknown."""
    return TAXONOMY[code]


def get_all_codes() -> List[DefectCode]:
    """All defect codes including OK and generic_bad."""
    return list(TAXONOMY.keys())


def get_v5_classes() -> List[DefectCode]:
    """Classes present in the V5 external dataset."""
    return [c for c, e in TAXONOMY.items() if e.in_v5_dataset]


def get_internal_only_classes() -> List[DefectCode]:
    """Defects that are NOT detectable from surface images."""
    return [c for c, e in TAXONOMY.items() if e.is_internal_only()]


def get_surface_classifiable_classes() -> List[DefectCode]:
    """Defect classes suitable for training a surface image classifier."""
    return [c for c, e in TAXONOMY.items() if e.surface_classifier_applicable]


def get_critical_severity_classes() -> List[DefectCode]:
    """Defect codes with CRITICAL severity."""
    return [c for c, e in TAXONOMY.items() if e.severity == DefectSeverity.CRITICAL]


def is_surface_detectable(code: DefectCode) -> bool:
    """True when this defect can be detected from a surface image alone."""
    return TAXONOMY[code].observability in (
        ObservabilityLevel.SURFACE_VISIBLE,
        ObservabilityLevel.SURFACE_INDICATOR,
    )


def requires_physical_confirmation(code: DefectCode) -> bool:
    """True when NDT or cross-section is required for a definitive verdict."""
    return TAXONOMY[code].requires_physical_confirmation()


TAXONOMY_VERSION = "P3D-1.0"
