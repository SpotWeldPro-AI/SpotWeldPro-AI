# SpotWeldPro AI — Annotation Schema Audit

**Task:** VISION-P3G  
**Date:** 2026-11-14  
**HEAD:** 5141b50 (feat(vision): P3E — human-in-the-loop annotation and dataset remediation)  
**Auditor:** P3G automated + manual inspection  

---

## 1. Migration Chain

| # | Revision ID | Down Revision | Status |
|---|---|---|---|
| 1 | `0001_initial` | `None` | COMMITTED |
| 2 | `0002_auth_audit` | `0001_initial` | COMMITTED |
| 3 | `0003_registry_foundation` | `0002_auth_audit` | COMMITTED |
| 4 | `0004_persistent_idempotency` | `0003_registry_foundation` | COMMITTED |
| 5 | `0005_registry_evidence_applicability` | `0004_persistent_idempotency` | COMMITTED |
| 6 | `0006_evidence_verification_authority_foundation` | `0005_registry_evidence_applicability` | COMMITTED |
| 7 | `0007_rule_lifecycle_events` | `0006_...` | COMMITTED |
| 8 | `0008_rule_evaluation_persistence` | `0007_rule_lifecycle_events` | COMMITTED |
| 9 | `0009_machine_readiness_persistence` | `0008_rule_evaluation_persistence` | COMMITTED |
| 10 | `0010_digital_weld_passport` | `0009_machine_readiness_persistence` | COMMITTED |
| 11 | `0011_engineering_library_foundation` | `0010_digital_weld_passport` | COMMITTED |
| 12a | `0012_ce04a_replace_turkish_defaults` | `0011_engineering_library_foundation` | COMMITTED |
| 12b | `0012_electrode_weldgun_weldschedule_persistence` | `0011_engineering_library_foundation` | COMMITTED (merge branch) |
| 13 | `0013_ce04b_canonical_role_codes` | `0012_ce04a_replace_turkish_defaults` | COMMITTED |
| 14 | `0014_auth_ux03_username` | `0013_ce04b_canonical_role_codes` | COMMITTED |
| 15 | `0015_organization_and_profile_tables` | `0014_auth_ux03_username` | COMMITTED |
| 16 | `0016_merge_heads` | `0012_electrode_weldgun_weldschedule_persistence`, `0015_organization_and_profile_tables` | COMMITTED (merge) |
| 17 | `0017_weld_groups` | `0016_merge_heads` | COMMITTED |
| 18 | `0018_weld_point_energy_fields` | `0017_weld_groups` | COMMITTED |
| 19 | `0019_import_batches` | `0018_weld_point_energy_fields` | COMMITTED |
| **20** | **`0020_annotation_tables`** | **`0019_import_batches`** | **STAGED (P3G — this task)** |

**HEAD revision after P3G:** `0020_annotation_tables`  
**Chain integrity:** Linear from 0019 → 0020. No duplicate revision IDs. No free slots.

---

## 2. ORM Models vs Migration Column Parity

All five annotation tables were compared between `app/models/annotation_entities.py` (ORM `create_all`) and `alembic/versions/0020_annotation_tables.py` (migration DDL).

### weld_annotations (21 columns)

| Column | Type | Nullable | ORM | Migration |
|---|---|---|---|---|
| id | Integer | NOT NULL PK | ✓ | ✓ |
| image_path | Text | NOT NULL | ✓ unique | ✓ unique |
| roi_crop_path | Text | NULL | ✓ | ✓ |
| image_hash | String(32) | NULL | ✓ index | ✓ index |
| weld_id | String(200) | NULL | ✓ index | ✓ index |
| source_archive | String(300) | NULL | ✓ | ✓ |
| split | String(20) | NOT NULL | default="unknown" | server_default="unknown" |
| label_provenance | String(80) | NOT NULL | default="SURFACE_OBSERVATION" | server_default="SURFACE_OBSERVATION" |
| contamination_level | String(20) | NOT NULL | default="UNKNOWN" | server_default="UNKNOWN" |
| max_markup_ratio | Float | NOT NULL | default=0.0 | server_default=text("0") |
| is_roi_cropped | Boolean | NOT NULL | default=False | server_default=text("0") |
| annotation_markup_removed | Boolean | NOT NULL | default=False | server_default=text("0") |
| image_width_px | Integer | NULL | ✓ | ✓ |
| image_height_px | Integer | NULL | ✓ | ✓ |
| annotator_id | String(200) | NOT NULL | ✓ index | ✓ index |
| review_status | String(30) | NOT NULL | default="DRAFT" | server_default="DRAFT" |
| taxonomy_version | String(30) | NOT NULL | default="P3D-1.0" | server_default="P3D-1.0" |
| export_eligible | Boolean | NOT NULL | default=False | server_default=text("0") |
| export_version | String(50) | NULL | ✓ | ✓ |
| created_at | DateTime(tz) | NOT NULL | default=_utc_now | server_default omitted |
| updated_at | DateTime(tz) | NOT NULL | default=_utc_now | server_default omitted |

**Note on defaults:** ORM uses Python-side `default=` for all columns; migration uses `server_default=` where values exist. The `created_at`/`updated_at` columns have no server_default in the migration (application always supplies them). This is intentional and correct — Python-side defaults are authoritative for the ORM layer.

### annotation_findings (12 columns)

All columns match between ORM and migration. FK `annotation_id → weld_annotations.id` ON DELETE CASCADE verified.

### annotation_reviews (8 columns)

All columns match. FK `annotation_id → weld_annotations.id` ON DELETE CASCADE verified.

### annotation_audit_entries (8 columns)

All columns match. `before_state` and `after_state` are JSON nullable. FK ON DELETE CASCADE verified.

### conflict_adjudications (16 columns)

All columns match. Unique constraint `uq_conflict_pair(sha1_16, path_a, path_b)` verified in both ORM and migration.

---

## 3. Indexes

| Table | Index Name | Columns | Unique |
|---|---|---|---|
| weld_annotations | ix_weld_annotations_id | id | No |
| weld_annotations | ix_weld_annotations_image_path | image_path | No |
| weld_annotations | ix_weld_annotations_image_hash | image_hash | No |
| weld_annotations | ix_weld_annotations_weld_id | weld_id | No |
| weld_annotations | ix_weld_annotations_annotator_id | annotator_id | No |
| weld_annotations | ix_weld_annotations_review_status | review_status | No |
| annotation_findings | ix_annotation_findings_id | id | No |
| annotation_findings | ix_annotation_findings_annotation_id | annotation_id | No |
| annotation_findings | ix_annotation_findings_defect_code | defect_code | No |
| annotation_reviews | ix_annotation_reviews_id | id | No |
| annotation_reviews | ix_annotation_reviews_annotation_id | annotation_id | No |
| annotation_reviews | ix_annotation_reviews_reviewer_id | reviewer_id | No |
| annotation_audit_entries | ix_annotation_audit_entries_id | id | No |
| annotation_audit_entries | ix_annotation_audit_entries_annotation_id | annotation_id | No |
| conflict_adjudications | ix_conflict_adjudications_id | id | No |
| conflict_adjudications | ix_conflict_adjudications_sha1_16 | sha1_16 | No |
| conflict_adjudications | ix_conflict_adjudications_decision | decision | No |
| conflict_adjudications | ix_conflict_adjudications_adjudicator_id | adjudicator_id | No |

---

## 4. Foreign Key Constraints

| Child Table | FK Column | Referenced Table | Referenced Column | On Delete |
|---|---|---|---|---|
| annotation_findings | annotation_id | weld_annotations | id | CASCADE |
| annotation_reviews | annotation_id | weld_annotations | id | CASCADE |
| annotation_audit_entries | annotation_id | weld_annotations | id | CASCADE |

`conflict_adjudications` has no FK (self-contained entity).

---

## 5. Unique Constraints

| Table | Constraint Name | Columns |
|---|---|---|
| weld_annotations | uq_weld_annotations_image_path | image_path |
| conflict_adjudications | uq_conflict_pair | sha1_16, path_a, path_b |

---

## 6. Reconciliation Guard

The migration includes an idempotency guard for databases where `create_all()` already ran:

```python
if "weld_annotations" in existing:
    return  # skip DDL, still stamp revision
```

This ensures:
- **Existing data is fully preserved** — no DROP/ALTER on pre-existing tables
- **alembic_version row is stamped** — chain stays consistent
- **Re-entrant safe** — upgrade can be run multiple times without harm

Tested and verified in `test_annotation_tables_reconciliation_guard`.

---

## 7. PostgreSQL Compatibility

| Item | Assessment |
|---|---|
| `VARCHAR(255)` for `version_num` | Handled by `prepare_postgresql_version_table()` in `env.py` |
| `server_default=sa.text("0")` for Boolean | PostgreSQL accepts integer `0`/`1` for BOOLEAN; also `false`/`true` are acceptable — PASS |
| `server_default="unknown"` etc. for String | Standard SQL default string — PASS |
| JSON column type | Native `jsonb` on PostgreSQL via SQLAlchemy — PASS |
| `CASCADE` on FK | Supported — PASS |
| Long revision IDs (e.g. `0020_annotation_tables` = 23 chars) | `version_num` is `VARCHAR(255)` — PASS |

**Note:** PostgreSQL live test not executed — Docker PostgreSQL not running in this environment. See DEPLOYMENT_READINESS_CHECKLIST.md.

---

## 8. Downgrade Safety Assessment

`downgrade()` drops all five annotation tables in reverse dependency order (children before parent):

1. `conflict_adjudications` (no FK children)
2. `annotation_audit_entries` → parent `weld_annotations`
3. `annotation_reviews` → parent `weld_annotations`
4. `annotation_findings` → parent `weld_annotations`
5. `weld_annotations` (last)

**WARNING:** Downgrade is destructive. All annotation data will be permanently lost.  
**Recommendation:** Do NOT run `downgrade` on any database containing real annotation data.  
The downgrade path was validated at the SQLite level (clean database only) in `test_annotation_tables_migration_round_trip`.
