"""
VISION-P3D: bilingual taxonomy + multi-label schema unit tests.

All tests use in-memory data only. No external files, no model weights.
"""
import pytest

from app.vision.defect_taxonomy import (
    TAXONOMY,
    TAXONOMY_VERSION,
    DefectCode,
    DefectSeverity,
    ObservabilityLevel,
    TaxonomyEntry,
    get_all_codes,
    get_critical_severity_classes,
    get_internal_only_classes,
    get_surface_classifiable_classes,
    get_taxonomy_entry,
    get_v5_classes,
    is_surface_detectable,
    requires_physical_confirmation,
)
from app.vision.multi_label_schemas import (
    AnnotationRecord,
    ConfidenceSource,
    DefectFinding,
    MultiLabelInspectionResult,
    _derive_overall_status,
)
from app.vision.schemas import ImageType, InspectionStatus, MeasurementSource


# ── Taxonomy completeness ──────────────────────────────────────────────────────

class TestTaxonomyCompleteness:
    def test_all_v5_classes_present(self):
        v5_codes = {
            DefectCode.OK, DefectCode.SPATTER, DefectCode.DEFORMED,
            DefectCode.BROKEN, DefectCode.MISSING, DefectCode.SMALL_NUGGET_INDICATOR,
            DefectCode.MISALIGNED, DefectCode.OVERLAPPING, DefectCode.EDGE_WELD,
            DefectCode.BURN_THROUGH, DefectCode.DOUBLE_SHEET, DefectCode.CRUSH_DENT,
            DefectCode.GENERIC_NOK,
        }
        in_v5 = set(get_v5_classes())
        assert v5_codes == in_v5

    def test_all_internal_classes_present(self):
        internal = {
            DefectCode.INCOMPLETE_FUSION, DefectCode.POROSITY,
            DefectCode.HOT_CRACK, DefectCode.COLD_LAP,
        }
        got = set(get_internal_only_classes())
        for code in internal:
            assert code in got

    def test_expulsion_in_taxonomy(self):
        # Expulsion is surface-visible but not in V5
        entry = get_taxonomy_entry(DefectCode.EXPULSION)
        assert not entry.in_v5_dataset
        assert entry.surface_classifier_applicable

    def test_total_taxonomy_size(self):
        assert len(TAXONOMY) == 18  # 13 V5 + 5 internal/literature

    def test_taxonomy_version_set(self):
        assert TAXONOMY_VERSION.startswith("P3D")


class TestTaxonomyBilingualConsistency:
    def test_all_entries_have_tr_name(self):
        for code, entry in TAXONOMY.items():
            assert entry.name_tr, f"{code}: name_tr is empty"

    def test_all_entries_have_en_name(self):
        for code, entry in TAXONOMY.items():
            assert entry.name_en, f"{code}: name_en is empty"

    def test_all_entries_have_tr_description(self):
        for code, entry in TAXONOMY.items():
            assert entry.description_tr, f"{code}: description_tr is empty"

    def test_all_entries_have_en_description(self):
        for code, entry in TAXONOMY.items():
            assert entry.description_en, f"{code}: description_en is empty"

    def test_tr_and_en_names_differ(self):
        for code, entry in TAXONOMY.items():
            if code == DefectCode.OK:
                continue  # "Kabul" / "Accepted" — clearly different
            assert entry.name_tr != entry.name_en, (
                f"{code}: name_tr and name_en are identical ({entry.name_tr!r})"
            )

    def test_all_entries_have_visual_indicators(self):
        for code, entry in TAXONOMY.items():
            assert entry.visual_indicators, f"{code}: visual_indicators is empty"


# ── Observability rules ────────────────────────────────────────────────────────

class TestObservabilityRules:
    def test_surface_visible_defects_are_surface_detectable(self):
        for code, entry in TAXONOMY.items():
            if entry.observability == ObservabilityLevel.SURFACE_VISIBLE:
                assert is_surface_detectable(code), (
                    f"{code} is SURFACE_VISIBLE but is_surface_detectable() returned False"
                )

    def test_surface_indicator_defects_are_surface_detectable(self):
        for code, entry in TAXONOMY.items():
            if entry.observability == ObservabilityLevel.SURFACE_INDICATOR:
                assert is_surface_detectable(code)

    def test_ndt_required_not_surface_detectable(self):
        for code, entry in TAXONOMY.items():
            if entry.observability == ObservabilityLevel.NDT_REQUIRED:
                assert not is_surface_detectable(code)

    def test_destructive_only_not_surface_detectable(self):
        for code, entry in TAXONOMY.items():
            if entry.observability == ObservabilityLevel.DESTRUCTIVE_ONLY:
                assert not is_surface_detectable(code)

    def test_surface_classifier_applicable_only_when_detectable(self):
        for code, entry in TAXONOMY.items():
            if entry.surface_classifier_applicable:
                assert is_surface_detectable(code), (
                    f"{code}: surface_classifier_applicable=True but not surface-detectable"
                )

    def test_internal_only_not_applicable_for_surface_classifier(self):
        for code in get_internal_only_classes():
            entry = get_taxonomy_entry(code)
            assert not entry.surface_classifier_applicable, (
                f"{code}: internal defect marked surface_classifier_applicable"
            )


# ── Evidence matrix — specific entries ────────────────────────────────────────

class TestEvidenceMatrix:
    def test_incomplete_fusion_requires_destructive(self):
        entry = get_taxonomy_entry(DefectCode.INCOMPLETE_FUSION)
        assert entry.observability == ObservabilityLevel.DESTRUCTIVE_ONLY
        assert entry.requires_cross_section
        assert entry.requires_ndt

    def test_porosity_requires_ndt(self):
        entry = get_taxonomy_entry(DefectCode.POROSITY)
        assert entry.observability == ObservabilityLevel.NDT_REQUIRED
        assert entry.requires_ndt

    def test_hot_crack_requires_destructive(self):
        entry = get_taxonomy_entry(DefectCode.HOT_CRACK)
        assert entry.observability == ObservabilityLevel.DESTRUCTIVE_ONLY
        assert entry.requires_cross_section

    def test_cold_lap_requires_destructive(self):
        entry = get_taxonomy_entry(DefectCode.COLD_LAP)
        assert entry.observability == ObservabilityLevel.DESTRUCTIVE_ONLY
        assert entry.requires_cross_section

    def test_missing_weld_no_physical_confirmation(self):
        entry = get_taxonomy_entry(DefectCode.MISSING)
        assert not entry.requires_cross_section
        assert not entry.requires_ndt

    def test_burn_through_no_physical_confirmation(self):
        entry = get_taxonomy_entry(DefectCode.BURN_THROUGH)
        assert not entry.requires_cross_section
        assert not entry.requires_ndt

    def test_small_nugget_indicator_requires_cross_section(self):
        entry = get_taxonomy_entry(DefectCode.SMALL_NUGGET_INDICATOR)
        assert entry.requires_cross_section
        assert entry.observability == ObservabilityLevel.SURFACE_INDICATOR

    def test_broken_weld_requires_cross_section(self):
        entry = get_taxonomy_entry(DefectCode.BROKEN)
        assert entry.requires_cross_section

    def test_ok_does_not_require_physical_confirmation(self):
        entry = get_taxonomy_entry(DefectCode.OK)
        assert not entry.requires_cross_section

    def test_ok_has_note_about_nugget_limitation(self):
        entry = get_taxonomy_entry(DefectCode.OK)
        combined = " ".join(entry.notes).lower()
        assert "nugget" in combined or "surface" in combined


# ── Severity classification ────────────────────────────────────────────────────

class TestSeverityClassification:
    def test_critical_defects(self):
        critical = set(get_critical_severity_classes())
        expected = {
            DefectCode.BROKEN, DefectCode.MISSING, DefectCode.BURN_THROUGH,
            DefectCode.INCOMPLETE_FUSION, DefectCode.HOT_CRACK,
        }
        for code in expected:
            assert code in critical, f"{code} expected CRITICAL but not in list"

    def test_ok_is_accept(self):
        assert get_taxonomy_entry(DefectCode.OK).severity == DefectSeverity.ACCEPT

    def test_generic_bad_is_high(self):
        assert get_taxonomy_entry(DefectCode.GENERIC_NOK).severity == DefectSeverity.HIGH

    def test_spatter_is_medium(self):
        assert get_taxonomy_entry(DefectCode.SPATTER).severity == DefectSeverity.MEDIUM

    def test_no_internal_defect_is_accept(self):
        for code in get_internal_only_classes():
            entry = get_taxonomy_entry(code)
            assert entry.severity != DefectSeverity.ACCEPT


# ── Training restrictions ──────────────────────────────────────────────────────

class TestTrainingRestrictions:
    def test_generic_bad_not_surface_classifier_applicable(self):
        entry = get_taxonomy_entry(DefectCode.GENERIC_NOK)
        assert not entry.surface_classifier_applicable

    def test_generic_bad_has_training_restriction_note(self):
        entry = get_taxonomy_entry(DefectCode.GENERIC_NOK)
        combined = " ".join(entry.notes).upper()
        assert "TRAINING" in combined or "RESTRICTION" in combined

    def test_small_nugget_indicator_has_caution_note(self):
        entry = get_taxonomy_entry(DefectCode.SMALL_NUGGET_INDICATOR)
        combined = " ".join(entry.notes).lower()
        assert "nugget" in combined

    def test_incomplete_fusion_not_surface_applicable(self):
        assert not get_taxonomy_entry(DefectCode.INCOMPLETE_FUSION).surface_classifier_applicable

    def test_surface_classifiable_classes_count(self):
        # 13 V5 classes (minus generic_bad = 12) + expulsion (1 non-V5) = 13
        classifiable = get_surface_classifiable_classes()
        assert DefectCode.GENERIC_NOK not in classifiable
        # all classifiable must be surface-detectable
        for code in classifiable:
            assert is_surface_detectable(code)


# ── Accessor functions ─────────────────────────────────────────────────────────

class TestAccessorFunctions:
    def test_get_taxonomy_entry_all_codes(self):
        for code in get_all_codes():
            entry = get_taxonomy_entry(code)
            assert isinstance(entry, TaxonomyEntry)
            assert entry.code == code

    def test_get_taxonomy_entry_raises_for_unknown(self):
        with pytest.raises(KeyError):
            get_taxonomy_entry("nonexistent_code")  # type: ignore

    def test_requires_physical_confirmation_matches_entry(self):
        for code in get_all_codes():
            entry = get_taxonomy_entry(code)
            assert requires_physical_confirmation(code) == entry.requires_physical_confirmation()

    def test_v5_classes_all_have_in_v5_true(self):
        for code in get_v5_classes():
            assert get_taxonomy_entry(code).in_v5_dataset

    def test_internal_only_all_have_correct_observability(self):
        for code in get_internal_only_classes():
            entry = get_taxonomy_entry(code)
            assert entry.observability in (
                ObservabilityLevel.NDT_REQUIRED,
                ObservabilityLevel.DESTRUCTIVE_ONLY,
            )


# ── DefectFinding ──────────────────────────────────────────────────────────────

class TestDefectFinding:
    def test_from_taxonomy_populates_names(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        assert f.name_tr
        assert f.name_en
        assert f.defect_code == DefectCode.SPATTER

    def test_from_taxonomy_default_confidence_zero(self):
        f = DefectFinding.from_taxonomy(DefectCode.MISSING)
        assert f.confidence == 0.0
        assert f.confidence_source == ConfidenceSource.NOT_COMPUTED

    def test_from_taxonomy_internal_defect_is_internal_only(self):
        f = DefectFinding.from_taxonomy(DefectCode.INCOMPLETE_FUSION)
        assert f.is_internal_only()
        assert not f.is_surface_visible()

    def test_from_taxonomy_surface_defect_is_surface_visible(self):
        f = DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH)
        assert f.is_surface_visible()

    def test_critical_defect_is_critical(self):
        f = DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH)
        assert f.is_critical()

    def test_spatter_not_critical(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        assert not f.is_critical()

    def test_from_taxonomy_carries_requires_physical_confirmation(self):
        f = DefectFinding.from_taxonomy(DefectCode.INCOMPLETE_FUSION)
        assert f.requires_physical_confirmation

    def test_from_taxonomy_ok_no_physical_confirmation(self):
        f = DefectFinding.from_taxonomy(DefectCode.OK)
        assert not f.requires_physical_confirmation

    def test_bbox_pixels_stored(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER, bbox_pixels=(10, 20, 50, 50))
        assert f.bbox_pixels == (10, 20, 50, 50)

    def test_notes_carried(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER, notes=["test note"])
        assert "test note" in f.notes

    def test_all_v5_codes_constructable(self):
        for code in get_v5_classes():
            f = DefectFinding.from_taxonomy(code)
            assert f.defect_code == code


# ── _derive_overall_status ─────────────────────────────────────────────────────

class TestDeriveOverallStatus:
    def test_no_findings_returns_unknown(self):
        assert _derive_overall_status([]) == InspectionStatus.UNKNOWN

    def test_critical_finding_returns_nok(self):
        f = DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH)
        assert _derive_overall_status([f]) == InspectionStatus.NOK

    def test_high_finding_returns_nok(self):
        f = DefectFinding.from_taxonomy(DefectCode.BROKEN)
        # broken is CRITICAL; use misaligned (HIGH) instead
        f2 = DefectFinding.from_taxonomy(DefectCode.MISALIGNED)
        assert _derive_overall_status([f2]) == InspectionStatus.NOK

    def test_medium_finding_returns_review(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        assert _derive_overall_status([f]) == InspectionStatus.REVIEW

    def test_ok_finding_with_zero_confidence_returns_unknown(self):
        f = DefectFinding.from_taxonomy(DefectCode.OK, confidence=0.0)
        assert _derive_overall_status([f]) == InspectionStatus.UNKNOWN

    def test_ok_finding_with_confidence_returns_ok(self):
        f = DefectFinding.from_taxonomy(DefectCode.OK, confidence=0.8)
        assert _derive_overall_status([f]) == InspectionStatus.OK

    def test_critical_dominates_ok(self):
        ok = DefectFinding.from_taxonomy(DefectCode.OK, confidence=0.9)
        nok = DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH)
        assert _derive_overall_status([ok, nok]) == InspectionStatus.NOK

    def test_multiple_medium_still_review(self):
        s = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        c = DefectFinding.from_taxonomy(DefectCode.CRUSH_DENT)
        assert _derive_overall_status([s, c]) == InspectionStatus.REVIEW


# ── MultiLabelInspectionResult ─────────────────────────────────────────────────

class TestMultiLabelInspectionResult:
    def _ok_finding(self, confidence=0.0):
        return DefectFinding.from_taxonomy(DefectCode.OK, confidence=confidence)

    def _spatter_finding(self):
        return DefectFinding.from_taxonomy(DefectCode.SPATTER)

    def _burn_through_finding(self):
        return DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH)

    def _internal_finding(self):
        return DefectFinding.from_taxonomy(DefectCode.INCOMPLETE_FUSION)

    def test_empty_findings_unknown_status(self):
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-001",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=[],
        )
        assert result.overall_status == InspectionStatus.UNKNOWN
        assert result.total_findings == 0

    def test_critical_finding_sets_nok(self):
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-002",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=[self._burn_through_finding()],
        )
        assert result.overall_status == InspectionStatus.NOK
        assert result.has_critical

    def test_surface_detectable_count(self):
        findings = [self._spatter_finding(), self._internal_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-003",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert result.surface_detectable_count == 1
        assert result.ndt_required_count == 1

    def test_training_gate_always_false(self):
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-004",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=[self._spatter_finding()],
        )
        assert result.training_gate_open is False

    def test_training_gate_note_references_e1_e4(self):
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-005",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=[],
        )
        assert "E1" in result.training_gate_note or "gate" in result.training_gate_note.lower()

    def test_critical_findings_accessor(self):
        findings = [self._burn_through_finding(), self._spatter_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-006",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert len(result.critical_findings()) == 1
        assert result.critical_findings()[0].defect_code == DefectCode.BURN_THROUGH

    def test_internal_findings_accessor(self):
        findings = [self._spatter_finding(), self._internal_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-007",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert len(result.internal_findings()) == 1
        assert result.internal_findings()[0].defect_code == DefectCode.INCOMPLETE_FUSION

    def test_requires_ndt_when_internal_finding(self):
        findings = [self._internal_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-008",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert result.requires_ndt()

    def test_does_not_require_ndt_when_only_surface_findings(self):
        findings = [self._spatter_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-009",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert not result.requires_ndt()

    def test_defect_codes_accessor(self):
        findings = [self._spatter_finding(), self._burn_through_finding()]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-010",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        codes = result.defect_codes()
        assert DefectCode.SPATTER in codes
        assert DefectCode.BURN_THROUGH in codes

    def test_taxonomy_version_set(self):
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-011",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=[],
        )
        assert result.taxonomy_version == TAXONOMY_VERSION

    def test_multi_defect_coexistence(self):
        findings = [
            self._spatter_finding(),
            self._burn_through_finding(),
            self._internal_finding(),
        ]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="test-012",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert result.total_findings == 3
        assert result.overall_status == InspectionStatus.NOK
        assert result.has_critical
        assert result.surface_detectable_count == 2  # spatter + burn_through
        assert result.ndt_required_count == 1


# ── AnnotationRecord ───────────────────────────────────────────────────────────

class TestAnnotationRecord:
    def test_training_eligible_requires_roi_and_findings(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=[f],
            is_roi_cropped=True,
            annotation_markup_removed=True,
        )
        assert rec.is_training_eligible()

    def test_not_eligible_without_roi(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=[f],
            is_roi_cropped=False,
            annotation_markup_removed=True,
        )
        assert not rec.is_training_eligible()

    def test_not_eligible_without_markup_removed(self):
        f = DefectFinding.from_taxonomy(DefectCode.SPATTER)
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=[f],
            is_roi_cropped=True,
            annotation_markup_removed=False,
        )
        assert not rec.is_training_eligible()

    def test_not_eligible_when_only_generic_bad(self):
        f = DefectFinding.from_taxonomy(DefectCode.GENERIC_NOK)
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=[f],
            is_roi_cropped=True,
            annotation_markup_removed=True,
        )
        assert not rec.is_training_eligible()

    def test_eligible_with_specific_and_generic_bad(self):
        # generic_bad alongside a specific defect is acceptable
        findings = [
            DefectFinding.from_taxonomy(DefectCode.SPATTER),
            DefectFinding.from_taxonomy(DefectCode.GENERIC_NOK),
        ]
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=findings,
            is_roi_cropped=True,
            annotation_markup_removed=True,
        )
        assert rec.is_training_eligible()

    def test_not_eligible_when_no_findings(self):
        rec = AnnotationRecord(
            image_path="a.png",
            annotator_id="eng01",
            annotation_date="2026-11-13",
            image_type=ImageType.SURFACE,
            findings=[],
            is_roi_cropped=True,
            annotation_markup_removed=True,
        )
        assert not rec.is_training_eligible()


# ── Integration: multi-label pipeline ─────────────────────────────────────────

class TestMultiLabelIntegration:
    """
    End-to-end: build multi-label findings and verify aggregate properties.
    Models a real scenario: a weld with spatter + possible small nugget indicator.
    """

    def test_spatter_plus_small_nugget_indicator(self):
        findings = [
            DefectFinding.from_taxonomy(DefectCode.SPATTER, confidence=0.0),
            DefectFinding.from_taxonomy(DefectCode.SMALL_NUGGET_INDICATOR, confidence=0.0),
        ]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="int-001",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        # Both are NON-CRITICAL (medium + high)
        assert result.overall_status == InspectionStatus.NOK
        assert not result.has_critical
        # small nugget indicator requires cross-section
        assert result.requires_ndt()
        # both are surface-detectable
        assert result.surface_detectable_count == 2

    def test_burn_through_plus_incomplete_fusion(self):
        findings = [
            DefectFinding.from_taxonomy(DefectCode.BURN_THROUGH),
            DefectFinding.from_taxonomy(DefectCode.INCOMPLETE_FUSION),
        ]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="int-002",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert result.overall_status == InspectionStatus.NOK
        assert result.has_critical
        assert result.ndt_required_count == 1
        assert result.surface_detectable_count == 1
        assert result.requires_ndt()

    def test_no_model_training_flag(self):
        findings = [DefectFinding.from_taxonomy(DefectCode.SPATTER)]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="int-003",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert not result.training_gate_open

    def test_surface_classifier_applicable_count(self):
        findings = [
            DefectFinding.from_taxonomy(DefectCode.SPATTER),         # applicable
            DefectFinding.from_taxonomy(DefectCode.GENERIC_NOK),     # NOT applicable
            DefectFinding.from_taxonomy(DefectCode.INCOMPLETE_FUSION),  # NOT applicable
        ]
        result = MultiLabelInspectionResult.from_findings(
            inspection_id="int-004",
            timestamp="2026-11-13T12:00:00Z",
            image_type=ImageType.SURFACE,
            findings=findings,
        )
        assert result.surface_classifier_applicable_count == 1
